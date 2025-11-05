from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Depends, File, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from posthog import Posthog
from typing import List
import traceback
import httpx
from .logic import check_question_limit
from .utils.redis import RedisSessionMiddleware, get_session, SessionManager
from .utils.dependencies import require_auth 
from .utils.pydantic_models import (
    LoginRequest, LoginResponse, AuthCheckResponse, GenerateSummaryRequest,
    RegenerateSummaryRequest, SaveSummaryRequest, GenerateQuizRequest,
    SaveQuizAnswersRequest, ToggleStarQuestionRequest, StarAllQuestionsRequest,
    LoadStudySetRequest, UpdateSetTitleRequest, DeleteQuestionSetRequest,
    RemoveUserPdfsRequest, SubmitFeedbackRequest, SuccessResponse,
    UserPdfsResponse, QuestionSetsResponse, QuizResponse, CurrentSessionSourcesResponse,
    UserTasksResponse, UploadResponse, TaskStatusResponse, UpdateSetTitleResponse,
    QuestionResponse, ShuffleQuizResponse, StarredQuizResponse, StarAllQuestionsResponse,
    LoadStudySetResponse, DeleteQuestionsRequest,
    SignUpRequest
)
from .open_ai_calls import randomize_answer_choices, gpt_summarize_transcript_chunked, generate_quiz_questions, generate_short_title
from .database import (
    upsert_pdf_results, check_question_set_exists,
    check_file_exists, generate_content_hash, generate_file_hash,
    authenticate_user, star_all_questions_by_hashes,
    upsert_question_set, upload_pdf_to_storage, get_question_sets_for_user, get_full_study_set_data, update_question_set_title,
    touch_question_set, update_question_starred_status, delete_question_set_and_questions, insert_feedback, 
    append_pdf_hash_to_user_pdfs, get_user_associated_pdf_metadata, get_pdf_text_by_hashes,
    update_user_task_status, get_user_tasks, delete_user_tasks_by_status, remove_pdf_hashes_from_user,
    create_user, redis_client, delete_questions_from_set
)
# Import the main Celery app instance from worker.py
from .background.worker import app as celery_app
from .background.tasks import print_number_task, process_pdf_task
import os
import re
from datetime import timedelta, datetime
import gc
import random
import json
import gzip
import asyncio
from celery.result import AsyncResult # Import this to interact with task results
import tempfile # Import tempfile for creating temporary files
from datetime import datetime, timezone # Import timezone for UTC


# Initialize PostHog for server-side tracking
posthog_api_key = os.environ.get('VITE_PUBLIC_POSTHOG_KEY')
posthog_host = os.environ.get('VITE_PUBLIC_POSTHOG_HOST')

if posthog_api_key:
    posthog = Posthog(posthog_api_key, host=posthog_host)
    print(f"PostHog initialized for server-side tracking: {posthog_host}")
else:
    posthog = None
    print("Warning: PostHog API key not found. Server-side exception tracking disabled.")


# Streaming flag
STREAMING_ENABLED = True

# Try absolute path resolution
static_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'client', 'dist')

# Create FastAPI app
app = FastAPI(
    title="Med Study API",
    description="Medical study application with AI-powered quiz generation",
    version="1.0.0"
)

# Custom exception handler to maintain Flask error format compatibility
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # Try to get user ID from session for exception tracking
    try:
        session = get_session(request)
        user_id = session.get('user_id') if session else None
        
        # Capture exception in PostHog with user context
        if posthog:
            posthog.capture_exception(
                exc, 
                distinct_id=user_id or 'anonymous',
                properties={
                    'status_code': exc.status_code,
                    'detail': exc.detail,
                    'path': request.url.path,
                    'method': request.method,
                    'user_id': user_id
                }
            )
    except Exception as e:
        # If PostHog tracking fails, don't break the error response
        print(f"Failed to track exception in PostHog: {e}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}  # Use "error" instead of "detail" for Flask compatibility
    )

# Configure CORS
# Get allowed origins from environment variable, fallback to localhost for development
ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS').split(',')
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Specific origins only
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Specific methods only
    allow_headers=[
        "Accept",
        "Accept-Language", 
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "X-CSRF-Token"
    ],
)

# Add Redis session middleware
app.add_middleware(RedisSessionMiddleware, session_cookie_name="session_id", session_ttl_hours=1)

# Mount static files
app.mount("/static", StaticFiles(directory=static_folder), name="static")

# Email validation regex
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

@app.post('/api/auth/login', response_model=LoginResponse)
async def login(request: LoginRequest, session: SessionManager = Depends(get_session)):
    print("login()")
    try:
        # Validate email format
        if not re.match(EMAIL_REGEX, request.email):
            raise HTTPException(status_code=400, detail='Invalid email format')

        # Authenticate user against database
        auth_result = authenticate_user(request.email, request.password)
        
        if not auth_result["success"]:
            print(f"Database error during authentication: {auth_result.get('error', 'Unknown error')}")
            raise HTTPException(status_code=500, detail='Authentication service unavailable')
            
        if not auth_result["authenticated"]:
            print(f"Invalid credentials for email: {request.email}")
            raise HTTPException(status_code=401, detail='Invalid credentials')

        print(f"User authenticated: {auth_result['user']}")
        user = auth_result["user"]
        
        # Clear any existing session data
        session.clear()
        print(f"User ID: {user['id']}")
        
        # Set new session data
        session['user_id'] = user['id']
        session['name'] = user['name']
        session['email'] = user['email']
        session['user_level'] = user['user_level']
        print(f"Session data set - user_id: {session.get('user_id')}, name: {session.get('name')}, email: {session.get('email')}, user_level: {session.get('user_level')}")
        
        # Track successful login in PostHog
        if posthog:
            posthog.capture(
                distinct_id=user['id'],
                event='user_login_server',
                properties={
                    'email': user['email'],
                    'name': user['name'],
                    'login_method': 'email_password',
                    'user_level': user['user_level']
                }
            )
        
        # Ensure PDF results are empty on fresh login
        session['summary'] = ""
        session['quiz_questions'] = []
        
        return LoginResponse(success=True)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/auth/signup', response_model=SuccessResponse)
async def signup(request: SignUpRequest):
    print("signup()")
    try:
        # Validate email format
        if not re.match(EMAIL_REGEX, request.email):
            raise HTTPException(status_code=400, detail='Invalid email format')
        
        # Create user in database. Use the provided name.
        create_user_result = create_user(request.email, request.password, request.name)

        if not create_user_result["success"]:
            if create_user_result.get("status_code") == 409:
                raise HTTPException(status_code=409, detail=create_user_result.get("error", "Account with this email already exists."))
            else:
                print(f"Database error during user creation: {create_user_result.get('error', 'Unknown error')}")
                raise HTTPException(status_code=500, detail=create_user_result.get("error", "User creation failed."))
        
        # Track successful signup in PostHog
        if posthog:
            posthog.capture(
                distinct_id=create_user_result.get('id', 'unknown'),
                event='user_signup_server',
                properties={
                    'email': request.email,
                    'name': request.name,
                    'signup_method': 'email_password'
                }
            )
        
        return SuccessResponse(success=True, message="User created successfully")

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error during signup: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/auth/logout', response_model=SuccessResponse)
async def logout(session: SessionManager = Depends(get_session)):
    print("logout()")
    try:
        # Explicitly clear PDF results and all session data
        session.clear()
        
        return SuccessResponse(success=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/api/auth/check', response_model=AuthCheckResponse)
async def check_auth(session: SessionManager = Depends(get_session)):
    print("check_auth()")
    try:
        print(f"Session state during auth check: user_id={session.get('user_id')}, name={session.get('name')}, email={session.get('email')}")
        if 'user_id' in session:
            # Get user email from session
            email = session.get('email')
            print(f"User authenticated in check_auth: {email}")
            # In a real app, you might want to fetch more user details from a database
            return AuthCheckResponse(
                authenticated=True,
                user={
                    'name': session.get('name'),
                    'email': email,
                    'id': session.get('user_id')
                },
                summary=session.get('summary', '')
            )
        return AuthCheckResponse(authenticated=False)
    except Exception as e:
        print(f"Error checking authentication status: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# New endpoint to get user's associated PDFs
@app.get('/api/get-user-pdfs', response_model=UserPdfsResponse)
async def get_user_pdfs(user_id: str = Depends(require_auth)):
    print(f"get_user_pdfs() called for user_id: {user_id} (type: {type(user_id)})")
    try:
        result = get_user_associated_pdf_metadata(user_id)
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=result.get('error', 'Failed to retrieve user PDFs'))
            
        return UserPdfsResponse(success=True, pdfs=result['data'])
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting user PDFs: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/generate-summary')
async def generate_summary(
    request: GenerateSummaryRequest,
    user_id: str = Depends(require_auth),
    session: SessionManager = Depends(get_session)
):
    print("generate_summary()")
    try:
        # Get additional user text if provided
        user_text = request.userText.strip() if request.userText else ""
        selected_pdf_hashes = request.selectedPdfHashes
        is_quiz_mode = str(request.isQuizMode).lower() == 'true'
        
        # Must have either selected PDFs or user text
        if not selected_pdf_hashes and not user_text:
            raise HTTPException(status_code=400, detail="No files or text provided")
                
        total_extracted_text = ""
        files_usertext_content = set()
        content_name_list = []

        # Process selected PDFs from database
        if selected_pdf_hashes:
            pdf_texts_result = get_pdf_text_by_hashes(selected_pdf_hashes)
            if not pdf_texts_result['success']:
                raise HTTPException(status_code=500, detail=f"Failed to retrieve PDF texts: {pdf_texts_result.get('error')}")
            
            pdf_texts_map = pdf_texts_result['data']
            for pdf_hash in selected_pdf_hashes:
                # Retrieve the object containing both text and filename
                pdf_data = pdf_texts_map.get(pdf_hash)
                if pdf_data and pdf_data.get('text'):
                    text = pdf_data['text']
                    filename = pdf_data['filename'] # Get the filename
                    print(f"Generate Summary with Filename: {filename}")

                    total_extracted_text += text
                    files_usertext_content.add(text) # Add text content for hash generation
                    if filename and filename not in content_name_list: # Add filename to list if not already present
                        content_name_list.append(filename)
                else:
                    print(f"Warning: Text for hash {pdf_hash[:8]}... not found in DB.")

        # Add user text if provided
        print(f"User text: {user_text[:100]}")
        if user_text:
            files_usertext_content.add(user_text)
            total_extracted_text += f"\n\nUser inputted text:\n{user_text}"
            content_name_list.append("User Text") # Indicate user text was included
        
        content_hash = generate_content_hash(files_usertext_content, user_id, is_quiz_mode)
        other_content_hash = generate_content_hash(files_usertext_content, user_id, not is_quiz_mode)

        session['content_hash'] = content_hash
        session['other_content_hash'] = other_content_hash
        session['content_name_list'] = content_name_list
        session['is_quiz_mode'] = is_quiz_mode # Store the quiz mode in the session

        if not total_extracted_text:
            raise HTTPException(status_code=400, detail="No text could be extracted from selected PDFs and no additional text provided")
        
        
        print(f"Text length being sent to AI: {len(total_extracted_text)} characters")
                
        if not STREAMING_ENABLED:
            summary = await gpt_summarize_transcript_chunked(total_extracted_text, stream=STREAMING_ENABLED) # Await the async function
            session['summary'] = summary
            return JSONResponse(content={'success': True, 'results': summary})
            
        # --- Streaming Response ---
        async def stream_generator(text_to_summarize): # Change to async def
            try:
                # 1) Immediately flush bytes to start the stream and defeat proxy buffering
                yield " " * 2048 + "\n"

                # 2) Kick off heavy work in the background
                task = asyncio.create_task(
                    gpt_summarize_transcript_chunked(text_to_summarize, stream=STREAMING_ENABLED)
                )

                # 3) Periodic heartbeats to keep the connection alive until the stream is ready
                while not task.done():
                    yield "[processing] summarizing chunks...\n"
                    await asyncio.sleep(5)

                # 4) When ready, stream the final summary
                stream_gen = await task
                async for chunk in stream_gen: # Await for chunks in streaming
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content

                # The session cannot be modified here. The client will send the final summary
                # to a different endpoint to be saved.
                gc.collect()
            except Exception as e:
                print(f"Error in gpt_summarize_transcript_chunked: {str(e)}")
                traceback.print_exc()
                # Convert the error to a JSON error response that can be streamed
                error_response = json.dumps({"error": str(e), "type": "streaming_error"})
                print(f"Streaming error response: {error_response}")
                yield error_response

        # Before streaming, save file-related info to the session. This is okay
        # because it happens within the initial request context.

        return StreamingResponse(
            stream_generator(total_extracted_text),
            media_type='text/plain',
            headers={'X-Accel-Buffering': 'no'}
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Force garbage collection to clean up memory
        gc.collect()


@app.post('/api/generate-quiz', response_model=QuizResponse)
async def generate_quiz(
    request: GenerateQuizRequest,
    user_id: str = Depends(require_auth),
    session: SessionManager = Depends(get_session)
):
    """Endpoint to generate quiz questions from the stored summary"""
    print(f"generate_quiz() called for user_id: {user_id}")

    num_questions = request.numQuestions  # Default to 5 if not specified
    is_quiz_mode = str(request.isQuizMode).lower() == 'true' # Default to False (study mode)

    try:
        user_level = session.get('user_level')
        print(f"User level: {user_level}")
        if user_level == "basic":
            check_question_limit(user_id, num_questions, is_quiz_mode)
    except HTTPException as e:
        pass
        # raise e
    except Exception as e:
        print(f"Error checking question limit: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    # Use Redis directly for the lock to ensure it's immediately available across requests
    lock_key = f"quiz_generation_lock:{user_id}"
    
    # Try to set the lock with a timeout (expires in 2 minutes as failsafe)
    lock_acquired = redis_client.set(lock_key, "locked", nx=True, ex=120) if redis_client else False
    
    if not lock_acquired:
        print(f"Quiz generation already in progress for user {user_id}, rejecting duplicate request")
        raise HTTPException(status_code=429, detail='Quiz generation already in progress. Please wait.')
    
    try:
        content_hash = session.get('content_hash')
        content_name_list = session.get('content_name_list', [])
        
        # Check if there's a summary to work with
        summary = session.get('summary', '')
        short_summary = session.get('short_summary', '')
        if not summary or not content_hash:
            print(f"No summary or content_hash available - returning 400")
            raise HTTPException(status_code=400, detail='No summary available. Please upload content first.')
        
        # Get request data and determine question type
        question_type = request.type  # 'initial', 'focused', or 'additional'
        incorrect_question_ids = request.incorrectQuestionIds
        previous_questions = session.get('quiz_questions', [])
        
        if previous_questions:
            previous_questions = previous_questions[-1]
        else:
            previous_questions = []

        print(f"Previous questions length: {len(previous_questions)}")

        is_previewing = request.isPreviewing
        diff_mode = request.diff_mode
        print(f"Question type: {question_type}, is_quiz_mode: {is_quiz_mode}, session is_quiz_mode: {session.get('is_quiz_mode')}")
        if question_type == 'initial' and is_quiz_mode != session.get('is_quiz_mode') and not diff_mode:
            prev_content_hash = session.get('content_hash')
            content_hash = session.get('other_content_hash')
            session['other_content_hash'] = prev_content_hash
            session['content_hash'] = content_hash
            print(f"Using other content hash: {content_hash}")
        else:
            content_hash = session.get('content_hash')
            print(f"Using content hash: {content_hash}")

        # Validate number of questions is within reasonable bounds
        if not isinstance(num_questions, int) or num_questions < 1 or num_questions > 20:
            num_questions = 5  # Default to 5 if invalid
        
        # For initial generation, check if we already have questions to prevent duplicates
        if question_type == 'initial':
            quiz_exists = check_question_set_exists(content_hash, user_id)['exists']
            if quiz_exists:
                print(f"Quiz set {content_hash} already exists for user {user_id}")
                return JSONResponse(
                    status_code=201,
                    content={'error': 'Quiz set already exists', 'content_hash': content_hash}
                )
        
        questions = []
        question_hashes = []
        if question_type != 'initial':
            # Generate questions (can be initial or focused based on parameters)
            questions, question_hashes = await generate_quiz_questions(
                summary, user_id, content_hash, 
                incorrect_question_ids=incorrect_question_ids, 
                previous_questions=previous_questions,
                num_questions=num_questions,
                is_quiz_mode=is_quiz_mode
            )

        other_content_hash = session.get('other_content_hash')
        
        # Only generate short title and upsert question set for initial generation
        if question_type == 'initial':
            short_summary = await generate_short_title(summary) # Await the async function
            # Upsert the question set to the database
            upsert_question_set(content_hash, other_content_hash, user_id, question_hashes, content_name_list, short_summary, summary, is_quiz_mode)
            session['short_summary'] = short_summary
        else:
            # For focused/additional questions, just upsert the new questions
            upsert_question_set(content_hash, other_content_hash, user_id, question_hashes, content_name_list, short_summary, summary, is_quiz_mode)
        
        # Store questions in session
        if is_previewing:
            # Store new questions in session, appending to the last set
            quiz_questions_sets = session.get('quiz_questions', [[]])
            # Get the last question set and extend it with the new questions.
            if quiz_questions_sets == []:
                quiz_questions_sets = [[]]
            quiz_questions_sets[-1].extend(questions)

            session['quiz_questions'] = quiz_questions_sets
        else:
            # Store new questions in session
            quiz_questions = session.get('quiz_questions', [])
            quiz_questions.append(questions)
            session['quiz_questions'] = quiz_questions
        
        return QuizResponse(
            success=True,
            questions=questions,
            short_summary=session.get('short_summary', ''),
            content_hash=content_hash,
            other_content_hash=other_content_hash
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating quiz questions: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Always clear the lock, whether success or failure
        if redis_client:
            redis_client.delete(lock_key)
        print(f"Quiz generation lock cleared for user {user_id}")



@app.get('/api/get-quiz', response_model=QuizResponse)
async def get_quiz(
    user_id: str = Depends(require_auth),
    session: SessionManager = Depends(get_session)
):
    """Endpoint to retrieve stored quiz questions"""
    print("get_quiz()")
    try:
        # Get stored questions
        questions = session.get('quiz_questions', [])
        latest_questions = questions[-1] if questions else []
        # print(f"Latest questions: {latest_questions}")
        
        return QuizResponse(
            success=True,
            questions=latest_questions,
            content_hash=session.get('content_hash', ''),
            other_content_hash=session.get('other_content_hash', '')
        )
    except Exception as e:
        print(f"Error retrieving quiz questions: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/get-other-quiz', response_model=QuizResponse)
async def get_other_quiz(
    user_id: str = Depends(require_auth),
    session: SessionManager = Depends(get_session)
):
    """Endpoint to retrieve stored quiz questions"""
    print("get_other_quiz()")
    try:
        # Get stored questions
        session['quiz_questions'] = []
        new_other_content_hash = session.get('content_hash')
        new_content_hash = session.get('other_content_hash')
        # print(session.get('content_hash'), session.get('other_content_hash'))
        session['content_hash'] = new_content_hash
        session['other_content_hash'] = new_other_content_hash
        # print(session.get('content_hash'), session.get('other_content_hash'))
        
        return QuizResponse(
            success=True,
            questions=[],
            content_hash=session.get('content_hash', ''),
            other_content_hash=session.get('other_content_hash', '')
        )
    except Exception as e:
        print(f"Error retrieving quiz questions: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    

@app.post('/api/save-quiz-answers', response_model=SuccessResponse)
async def save_quiz_answers(
    request: SaveQuizAnswersRequest,
    user_id: str = Depends(require_auth),
    session: SessionManager = Depends(get_session)
):
    """Endpoint to save user answers for the current quiz set"""
    print("save_quiz_answers()")
    try:
        # Get the request data
        user_answers = request.userAnswers
        submitted_answers = request.submittedAnswers
        
        # Get current quiz questions
        quiz_questions = session.get('quiz_questions', [])
        if not quiz_questions:
            raise HTTPException(status_code=400, detail='No quiz questions found')
            
        # Update the latest question set with user answers
        latest_question_set = quiz_questions[-1]
        
        for question in latest_question_set:
            question_id = question['id']
            question_id_str = str(question_id)  # Convert to string for JSON key comparison
            
            if question_id_str in user_answers and question_id_str in submitted_answers:
                question['userAnswer'] = user_answers[question_id_str]
                question['isAnswered'] = True
            else:
                question['userAnswer'] = None
                question['isAnswered'] = False
        
        # Save back to session
        session['quiz_questions'] = quiz_questions
        
        return SuccessResponse(success=True)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error saving quiz answers: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/regenerate-summary')
async def regenerate_summary(
    request: RegenerateSummaryRequest,
    user_id: str = Depends(require_auth),
    session: SessionManager = Depends(get_session)
):
    """Endpoint to regenerate the summary from stored text"""
    print("regenerate_summary()")
    try:
        # Get additional user text if provided
        user_text = request.userText.strip() if request.userText else ""
        selected_pdf_hashes = request.selectedPdfHashes
        
        # Must have either selected PDFs or user text
        if not selected_pdf_hashes and not user_text:
            raise HTTPException(status_code=400, detail="No files or text provided")
        
        total_extracted_text = ""
        # Process selected PDFs from database
        if selected_pdf_hashes:
            pdf_texts_result = get_pdf_text_by_hashes(selected_pdf_hashes)
            if not pdf_texts_result['success']:
                raise HTTPException(status_code=500, detail=f"Failed to retrieve PDF texts: {pdf_texts_result.get('error')}")
            
            pdf_texts_map = pdf_texts_result['data']
            for pdf_hash in selected_pdf_hashes:
                # Retrieve the object containing both text and filename
                pdf_data = pdf_texts_map.get(pdf_hash)
                if pdf_data and pdf_data.get('text'):
                    text = pdf_data['text']

                    total_extracted_text += text
                else:
                    print(f"Warning: Text for hash {pdf_hash[:8]}... not found in DB.")

        # Add user text if provided
        print(f"User text: {user_text[:100]}")
        if user_text:
            total_extracted_text += f"\n\nUser inputted text:\n{user_text}"

        # Must have text to regenerate from
        if not total_extracted_text:
            raise HTTPException(status_code=400, detail='No text available to regenerate summary from. Please upload content first.')
        
        # Generate new summary
        if not STREAMING_ENABLED:
            summary = await gpt_summarize_transcript_chunked(total_extracted_text, temperature=0.4, stream=STREAMING_ENABLED)
            session['summary'] = summary
            session['quiz_questions'] = []
            return JSONResponse(content={'success': True, 'summary': summary})

        # --- Streaming Response ---
        async def stream_generator(text_to_summarize):
            try:
                # 1) Immediately flush bytes to start the stream
                yield " " * 2048 + "\n"

                # 2) Kick off heavy work in the background
                task = asyncio.create_task(
                    gpt_summarize_transcript_chunked(text_to_summarize, temperature=0.4, stream=STREAMING_ENABLED)
                )

                # 3) Periodic heartbeats
                while not task.done():
                    yield "[processing] summarizing chunks...\n"
                    await asyncio.sleep(5)

                # 4) When ready, stream the final summary
                stream_gen = await task
                async for chunk in stream_gen:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
                
                # Redis session cannot be modified here.
                print("Redis session not modified, streaming complete (regenerate).")
            except Exception as e:
                print(f"Error in gpt_summarize_transcript_chunked (regenerate): {str(e)}")
                traceback.print_exc()
                # Convert the error to a JSON error response that can be streamed
                error_response = json.dumps({"error": str(e), "type": "streaming_error"})
                print(f"Streaming error response (regenerate): {error_response}")
                yield error_response

        # Clear old questions
        session['quiz_questions'] = []

        return StreamingResponse(
            stream_generator(total_extracted_text),
            media_type='text/plain',
            headers={'X-Accel-Buffering': 'no'}
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error regenerating summary: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/save-summary', response_model=SuccessResponse)
async def save_summary(
    request: SaveSummaryRequest,
    user_id: str = Depends(require_auth),
    session: SessionManager = Depends(get_session)
):
    """Endpoint to save the completed summary to the session."""
    print("save_summary()")
    try:
        summary = request.summary

        if not summary:
            raise HTTPException(status_code=400, detail='No summary provided')

        session['summary'] = summary
        # Clear any old quiz questions, as they are now outdated
        session['quiz_questions'] = []
        
        print("Summary successfully saved to session.")
        return SuccessResponse(success=True)

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error saving summary: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/api/get-question-sets', response_model=QuestionSetsResponse)
async def get_question_sets(user_id: str = Depends(require_auth)):
    """Endpoint to retrieve all study sets for the logged-in user."""
    print("get_question_sets()")
    try:
        result = get_question_sets_for_user(user_id)
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=result.get('error', 'Failed to get question sets'))
            
        return QuestionSetsResponse(success=True, sets=result['data'])
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting question sets: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/load-study-set', response_model=LoadStudySetResponse)
async def load_study_set(
    request: LoadStudySetRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(require_auth),
    session: SessionManager = Depends(get_session)
):
    """Endpoint to load a full study set into the user's session."""
    print("load_study_set()")
    try:
        content_hash = request.content_hash
        
        if not content_hash:
            raise HTTPException(status_code=400, detail='content_hash is required')
            
        # Run the timestamp update in the background as it's not critical for the response
        background_tasks.add_task(touch_question_set, content_hash, user_id)

        result = get_full_study_set_data(content_hash, user_id)
        print(f"get_full_study_set_data() result: {len(result['data']['quiz_questions'])}")
        
        if not result['success']:
            print(f"Failed to get study set data: {result.get('error')}")
            raise HTTPException(status_code=500, detail=result.get('error', 'Failed to load study set'))
        
        # Load data into session
        set_data = result['data']
        # Ensure summary is a string, not None, to prevent crashes.
        summary_text = set_data.get('summary', '')
        session['summary'] = summary_text
        session['short_summary'] = set_data.get('short_summary', '')
        session['quiz_questions'] = set_data.get('quiz_questions', [])
        session['content_hash'] = set_data.get('content_hash', '')
        session['other_content_hash'] = set_data.get('other_content_hash', '')
        session['content_name_list'] = set_data.get('content_name_list', [])
        
        print(f"Loaded {len(session.get('quiz_questions', []))} question sets into session.")
        return LoadStudySetResponse(success=True, summary=summary_text, content_hash=session['content_hash'], other_content_hash=session['other_content_hash'])
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error loading study set: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/api/get-current-session-sources', response_model=CurrentSessionSourcesResponse)
async def get_current_session_sources(
    user_id: str = Depends(require_auth),
    session: SessionManager = Depends(get_session)
):
    print("get_current_session_sources()")
    try:
        # Retrieve the content_name_list from the session
        content_names = session.get('content_name_list', [])
        return CurrentSessionSourcesResponse(
            success=True, 
            content_names=content_names, 
            short_summary=session.get('short_summary', '')
        )
    except Exception as e:
        print(f"Error getting current session sources: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/update-set-title', response_model=UpdateSetTitleResponse)
async def update_set_title(
    request: UpdateSetTitleRequest,
    user_id: str = Depends(require_auth),
    session: SessionManager = Depends(get_session)
):
    """Endpoint to update the title of a study set."""
    print("update_set_title()")
    try:
        if not request.content_hash or not request.new_title:
            raise HTTPException(status_code=400, detail='content_hash and new_title are required')
            
        result = update_question_set_title(request.content_hash, user_id, request.new_title)
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=result.get('error', 'Failed to update title'))
            
        # Supabase returns a list for updates; response model expects a dict
        updated_data = result.get('data', {})
        if isinstance(updated_data, list):
            updated_data = updated_data[0] if updated_data else {}
        
        # Update session if this is the currently loaded set
        current_content_hash = session.get('content_hash')
        if current_content_hash == request.content_hash:
            session['short_summary'] = request.new_title
            print(f"Updated session short_summary to: {request.new_title}")
        
        return UpdateSetTitleResponse(success=True, data=updated_data)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating set title: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/clear-session-content', response_model=SuccessResponse)
async def clear_session_content(
    user_id: str = Depends(require_auth),
    session: SessionManager = Depends(get_session)
):
    """Endpoint to clear session data related to a study set."""
    print("clear_session_content()")
    try:
        session.clear_content()
        
        return SuccessResponse(success=True, message='Session content cleared.')
    except Exception as e:
        print(f"Error clearing session content: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/toggle-star-question', response_model=QuestionResponse)
async def toggle_star_question(
    request: ToggleStarQuestionRequest,
    user_id: str = Depends(require_auth),
    session: SessionManager = Depends(get_session)
):
    print("toggle_star_question()")
    try:
        question_id = request.questionId

        if not question_id:
            raise HTTPException(status_code=400, detail='Question ID is required')
            
        quiz_questions_sets = session.get('quiz_questions', [])
        updated_question = None

        # Iterate through all question sets and questions to find and update the question
        for q_set in quiz_questions_sets:
            for question in q_set:
                # Make sure question ID is a string for consistent comparison if UUIDs are used.
                if str(question.get('id')) == str(question_id):
                    # Toggle the starred status locally in the session
                    new_starred_status = not question.get('starred', False)
                    question['starred'] = new_starred_status
                    updated_question = question

                    # Call database function to persist the change
                    # Ensure question has a 'hash' to update in DB
                    question_hash = question.get('hash')
                    if question_hash:
                        db_update_result = update_question_starred_status(question_hash, new_starred_status)
                        if not db_update_result['success']:
                            print(f"Warning: Failed to update star status in DB for {question_hash}: {db_update_result.get('error')}")
                    else:
                        print(f"Warning: Question {question_id} has no hash. Star status not persisted to DB.")

                    break
            if updated_question:
                break
        
        if updated_question:
            session['quiz_questions'] = quiz_questions_sets
            print(f"Toggled star for question ID {question_id}. New status: {updated_question.get('starred')}")
            return QuestionResponse(success=True, question=updated_question)
        else:
            print(f"Question with ID {question_id} not found.")
            raise HTTPException(status_code=404, detail='Question not found')

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error toggling star status: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/shuffle-quiz', response_model=ShuffleQuizResponse)
async def shuffle_quiz(
    user_id: str = Depends(require_auth),
    session: SessionManager = Depends(get_session)
):
    print("shuffle_quiz()")
    try:
        quiz_questions_sets = session.get('quiz_questions', [])
        
        if not quiz_questions_sets:
            return ShuffleQuizResponse(success=True, questions=[])
            
        # Get the latest set of questions
        latest_questions = quiz_questions_sets[-1]
        
        # Apply Fisher-Yates shuffle algorithm
        shuffled_questions = list(latest_questions)
        random.shuffle(shuffled_questions)
        for question in shuffled_questions:
            randomize_answer_choices(question)
        
        # Update the latest set in session with shuffled questions
        quiz_questions_sets[-1] = shuffled_questions
        session['quiz_questions'] = quiz_questions_sets
        
        print(f"Shuffled {len(shuffled_questions)} questions in session.")
        return ShuffleQuizResponse(success=True, questions=shuffled_questions)
    except Exception as e:
        print(f"Error shuffling quiz questions: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/start-starred-quiz', response_model=StarredQuizResponse)
async def start_starred_quiz(
    user_id: str = Depends(require_auth),
    session: SessionManager = Depends(get_session)
):
    print("start_starred_quiz()")
    try:
        quiz_questions_sets = session.get('quiz_questions', [])
        
        if not quiz_questions_sets:
            return StarredQuizResponse(success=True, questions=[])

        # Get the latest set of questions from the session
        latest_questions = quiz_questions_sets[-1]
        
        # Filter for only starred questions
        starred_questions = [q for q in latest_questions if q.get('starred', False)]

        if not starred_questions:
            return StarredQuizResponse(success=False, error='No starred questions found to start a quiz.', questions=[])
            
        # Replace the current (latest) quiz set in the session with only the starred questions
        # This effectively creates a new quiz from existing starred questions
        quiz_questions_sets[-1] = starred_questions
        session['quiz_questions'] = quiz_questions_sets
        
        print(f"Started quiz with {len(starred_questions)} starred questions.")
        return StarredQuizResponse(success=True, questions=starred_questions)
    except Exception as e:
        print(f"Error starting starred quiz: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/star-all-questions', response_model=StarAllQuestionsResponse)
async def star_all_questions(
    request: StarAllQuestionsRequest,
    user_id: str = Depends(require_auth),
    session: SessionManager = Depends(get_session)
):
    print("star_all_questions()")
    try:
        action = request.action  # 'star' or 'unstar'
        
        if action not in ['star', 'unstar']:
            raise HTTPException(status_code=400, detail='Invalid action. Must be "star" or "unstar"')
        
        quiz_questions_sets = session.get('quiz_questions', [])
        
        if not quiz_questions_sets:
            return StarAllQuestionsResponse(success=True, questions=[])

        # Get the latest set of questions from the session
        latest_questions = quiz_questions_sets[-1]
        
        # Update all questions based on action
        starred_status = action == 'star'
        updated_questions = []
        question_hashes = []
        
        for question in latest_questions:
            question['starred'] = starred_status
            updated_questions.append(question)
            
            # Collect question hashes for database update
            question_hash = question.get('hash')
            if question_hash:
                question_hashes.append(question_hash)
        
        # Update database for all questions
        if question_hashes:
            db_result = star_all_questions_by_hashes(question_hashes, starred_status)
            if not db_result['success']:
                print(f"Warning: Failed to update star status in DB: {db_result.get('error')}")
        
        # Update session
        quiz_questions_sets[-1] = updated_questions
        session['quiz_questions'] = quiz_questions_sets
        
        action_verb = "Starred" if starred_status else "Unstarred"
        print(f"{action_verb} all {len(updated_questions)} questions.")
        return StarAllQuestionsResponse(success=True, questions=updated_questions)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error {request.action}ring all questions: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/delete-questions', response_model=SuccessResponse)
async def delete_questions(
    request: DeleteQuestionsRequest,
    user_id: str = Depends(require_auth),
    session: SessionManager = Depends(get_session)
):
    print("delete_questions()")
    try:
        content_hash = request.content_hash
        question_hashes = request.question_hashes
        
        if not content_hash or not question_hashes:
            raise HTTPException(status_code=400, detail='content_hash and question_hashes are required')
        
        # Delete questions from database and update question set
        delete_result = delete_questions_from_set(content_hash, user_id, question_hashes)
        
        if not delete_result['success']:
            raise HTTPException(status_code=500, detail=delete_result.get('error', 'Failed to delete questions'))
        
        # Update session if this is the currently loaded set
        current_content_hash = session.get('content_hash')
        if current_content_hash == content_hash:
            quiz_questions_sets = session.get('quiz_questions', [])
            
            if quiz_questions_sets:
                # Remove questions from the latest question set in session
                latest_questions = quiz_questions_sets[-1]
                updated_questions = [
                    q for q in latest_questions 
                    if q.get('hash') not in question_hashes
                ]
                
                quiz_questions_sets[-1] = updated_questions
                session['quiz_questions'] = quiz_questions_sets
                
                print(f"Removed {len(latest_questions) - len(updated_questions)} questions from session")
        
        return SuccessResponse(
            success=True, 
            message=f'Successfully deleted {delete_result.get("deleted_count", 0)} questions from the question set'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting questions: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/delete-question-set', response_model=SuccessResponse)
async def delete_question_set(
    request: DeleteQuestionSetRequest,
    user_id: str = Depends(require_auth),
    session: SessionManager = Depends(get_session)
):
    print("delete_question_set()")
    try:
        content_hash = request.content_hash
        
        if not content_hash:
            raise HTTPException(status_code=400, detail='content_hash is required')
        
        # Delete the question set and associated questions from database
        delete_result = delete_question_set_and_questions(content_hash, user_id)
        
        if not delete_result['success']:
            raise HTTPException(status_code=500, detail=delete_result.get('error', 'Failed to delete question set'))
        
        # Clear session data if the deleted set is currently loaded
        current_content_hash = session.get('content_hash')
        if current_content_hash == content_hash:
            session.clear_content()
            print(f"Cleared session data for deleted set: {content_hash}")
        
        return SuccessResponse(success=True, message='Question set deleted successfully')
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting question set: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/submit-feedback', response_model=SuccessResponse)
async def submit_feedback(
    request: SubmitFeedbackRequest,
    user_id: str = Depends(require_auth),
    session: SessionManager = Depends(get_session)
):
    print("submit_feedback()")
    try:
        feedback_text = request.feedback
        user_name = session.get('name')
        user_email = session.get('email')

        if not feedback_text or not feedback_text.strip():
            raise HTTPException(status_code=400, detail='Feedback text cannot be empty')

        result = insert_feedback(user_id, user_email, user_name, feedback_text)
        
        if result['success']:
            return SuccessResponse(success=True, message='Feedback submitted successfully.')
        else:
            raise HTTPException(status_code=500, detail=result.get('error', 'Failed to submit feedback.'))

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error submitting feedback: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/clear-completed-tasks', response_model=SuccessResponse)
async def clear_completed_tasks_endpoint(user_id: str = Depends(require_auth)):
    print("clear_completed_tasks_endpoint()")
    try:
        # Define statuses to clear: SUCCESS and FAILURE
        statuses_to_clear = ['SUCCESS', 'FAILURE']
        
        result = delete_user_tasks_by_status(user_id, statuses_to_clear)
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=result.get('error', 'Failed to clear tasks'))
            
        return SuccessResponse(success=True, message=f"Cleared {result.get('deleted_count', 0)} completed tasks.")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error clearing completed tasks: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/remove-user-pdfs', response_model=SuccessResponse)
async def remove_user_pdfs_endpoint(
    request: RemoveUserPdfsRequest,
    user_id: str = Depends(require_auth)
):
    print("remove_user_pdfs_endpoint()")
    try:
        pdf_hashes = request.pdf_hashes

        if not pdf_hashes:
            raise HTTPException(status_code=400, detail='No PDF hashes provided for removal.')

        result = remove_pdf_hashes_from_user(user_id, pdf_hashes)
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=result.get('error', 'Failed to remove PDFs'))
            
        return SuccessResponse(success=True, message=f"Removed {result.get('deleted_count', 0)} PDFs from your account.")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error removing user PDFs: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/api/get-user-tasks', response_model=UserTasksResponse)
async def get_user_tasks_endpoint(user_id: str = Depends(require_auth)):
    print("get_user_tasks()")
    try:
        result = get_user_tasks(user_id)
        
        if not result['success']:
            print(f"Error retrieving tasks from Redis for user {user_id}: {result.get('error', 'Unknown error')}")
            raise HTTPException(status_code=500, detail=result.get('error', 'Failed to get tasks'))
        
        print(f"Tasks retrieved from Redis for user {user_id}:")
        for task in result['data']:
            print(f"  Task ID: {task.get('task_id', '')}, Filename: {task.get('filename', '')}, Status: {task.get('status', '')}, Message: {task.get('message', '')}")
                
        return UserTasksResponse(success=True, tasks=result['data'])
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_user_tasks_endpoint: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/upload-pdfs', response_model=UploadResponse)
async def upload_pdfs(
    files: List[UploadFile] = File(...),
    user_id: str = Depends(require_auth)
):
    print("upload_pdfs()")
    try:
        if not files:
            raise HTTPException(status_code=400, detail='No selected files')

        bucket_name = "pdfs"
        uploaded_task_details = []
        uploaded_files_details = []
        failed_files_details = []

        for file in files:
            if file.filename == '':
                continue

            print(f"Uploading file: {file.filename}")
            
            temp_file_path = None # Initialize to None
            try:
                # Create a temporary file to store the incoming PDF stream
                # delete=True ensures the file is automatically deleted when closed
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                    content = await file.read() # Read the file content
                    temp_file.write(content)
                    temp_file_path = temp_file.name # Get the path to the temporary file
                
                original_filename = file.filename
                
                # Generate hash of the content from the temporary file
                file_hash = generate_file_hash(temp_file_path)
                print(f"File hash: {file_hash}")

                # Check if file content already exists in our 'pdfs' table
                file_exists_result = check_file_exists(file_hash)

                if not file_exists_result['exists']:
                    # If file content is new, upload to Supabase Storage from the temporary file
                    upload_result = upload_pdf_to_storage(temp_file_path, file_hash, original_filename, bucket_name)

                    if not upload_result['success']:
                        print(f"Error uploading {original_filename} to Supabase Storage: {upload_result.get('error')}")
                        failed_files_details.append({'filename': original_filename, 'error': upload_result.get('error', 'Unknown upload error')})
                        continue # Skip to next file if upload to storage failed
                    
                    # Upsert PDF metadata to 'pdfs' table (linking storage URL and path)
                    pdf_metadata = {
                        "hash": file_hash,
                        "filename": original_filename,
                        "bucket_name": bucket_name,
                        "storage_file_path": upload_result['path'],
                        "text": "", # Text will be extracted by background task
                        "created_at": datetime.now().isoformat()
                    }
                    upsert_pdf_results_result = upsert_pdf_results(pdf_metadata)

                    if not upsert_pdf_results_result['success']:
                        print(f"Error upserting PDF results for {original_filename}: {upsert_pdf_results_result.get('error')}")
                        failed_files_details.append({'filename': original_filename, 'error': upsert_pdf_results_result.get('error', 'Unknown database error')})
                        continue # Skip to next file if DB upsert failed
                    
                    # Dispatch the Celery task to process the PDF text (using the hash to retrieve from Supabase)
                    task = process_pdf_task.delay(file_hash, bucket_name, upload_result['path'], user_id, original_filename)
                    uploaded_task_details.append({'filename': original_filename, 'task_id': task.id, 'file_hash': file_hash})
                    uploaded_files_details.append({'filename': original_filename, 'message': 'Uploaded and queued for processing.'})
                    
                    # Store initial task status in Redis
                    update_user_task_status(
                        user_id=user_id,
                        task_id=task.id,
                        filename=original_filename,
                        status='PENDING',
                        message=f'Task is queued for processing'
                    )

                else:
                    print(f"File with hash {file_hash[:8]}... already exists in storage. Skipping re-upload.")
                    # Even if file exists, ensure it's linked to this user
                    append_result = append_pdf_hash_to_user_pdfs(user_id, file_hash)
                    if not append_result['success']:
                        print(f"Error linking existing PDF {file_hash[:8]}... to user {user_id}: {append_result.get('error')}")
                        failed_files_details.append({'filename': original_filename, 'error': append_result.get('error', 'Failed to link file to user')})
                        continue
                    # For display purposes, treat existing files as successfully "uploaded"
                    uploaded_files_details.append({'filename': original_filename, 'message': 'Uploaded and queued for processing.'})

            except Exception as e:
                print(f"An unexpected error occurred for file {file.filename}: {str(e)}")
                failed_files_details.append({'filename': original_filename, 'error': str(e)})
            finally:
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        # Explicitly close the file handle before attempting to remove it
                        if 'temp_file' in locals() and not temp_file.closed:
                            temp_file.close()
                        os.remove(temp_file_path) # Ensure temporary file is deleted
                    except Exception as e_clean:
                        print(f"Error cleaning up temporary file {temp_file_path}: {str(e_clean)}")
        
        if not uploaded_task_details and not failed_files_details and not uploaded_files_details:
            return UploadResponse(
                success=False,
                message='No valid PDF files were provided or processed.',
                uploaded_files=[],
                failed_files=[],
                task_details=[]
            )

        return UploadResponse(
            success=True,
            message=f'{len(uploaded_files_details)} files uploaded, {len(failed_files_details)} files failed.',
            uploaded_files=uploaded_files_details,
            failed_files=failed_files_details,
            task_details=uploaded_task_details
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error uploading PDFs: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/pdf-processing-status/{task_id}", response_model=TaskStatusResponse)
async def get_pdf_processing_status(task_id: str, user_id: str = Depends(require_auth)):
    print(f"Checking status for task_id: {task_id}")
    try:
        task_result = AsyncResult(task_id, app=celery_app)
        
        status = task_result.status
        result = task_result.result # This will be the return value of the task if successful

        # Handle specific states
        if status == 'PENDING':
            # Task is not yet ready or does not exist
            timestamp = datetime.now(timezone.utc).strftime("%m-%d %H:%M")
            message = f"Task is queued for processing (UTC {timestamp})"
        elif status == 'IN PROGRESS' or status == 'STARTED':
            # Get the message from the meta information
            message = task_result.info.get('message', 'Task is in progress...')
        elif status == 'SUCCESS':
            message = task_result.info.get('message', 'Task completed successfully')
        elif status == 'FAILURE':
            # For a failed task, the `result` attribute typically contains the exception.
            # The `info` field might contain our last custom progress message or the exception itself.
            # We check if `info` is a dictionary; if so, we get our message. Otherwise, the exception is the message.
            if isinstance(task_result.info, dict):
                message = task_result.info.get('message', str(task_result.result))
            else:
                message = str(task_result.result)
        else:
            message = f"Task status: {status}"

        # Sanitize the result for JSON serialization if it's an exception object
        json_safe_result = result
        if isinstance(result, Exception):
            json_safe_result = str(result)

        return TaskStatusResponse(
            success=True,
            task_id=task_id,
            status=status,
            result=json_safe_result,
            message=message
        )

    except Exception as e:
        print(f"Error checking task status: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Serve the React frontend
@app.get("/")
async def serve():
    """Serve the main React app"""
    print(f"Serving main React app from: {static_folder}")
    try:
        return FileResponse(os.path.join(static_folder, 'index.html'))
    except Exception as e:
        print(f"Error serving index.html: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to serve index.html: {str(e)}")

@app.get('/favicon.png')
async def favicon():
    # Serve the favicon from the React build output
    try:
        return FileResponse(os.path.join(static_folder, 'favicon.png'), media_type='image/png')
    except Exception as e:
        print(f"Error serving favicon.png: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to serve favicon.png: {str(e)}")

# PostHog Analytics Reverse Proxy (to avoid adblockers)
@app.api_route("/ingest/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def proxy_posthog(request: Request, path: str, session: SessionManager = Depends(get_session)):
    """Proxy PostHog requests through our domain to avoid adblockers and inject user ID"""
    
    # PostHog's actual endpoint
    posthog_url = f"https://app.posthog.com/{path}"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get request body if it exists
            body = await request.body() if request.method in ["POST", "PUT", "PATCH"] else None
            
            # Inject user ID into PostHog requests if user is authenticated
            if body and request.method == "POST":
                try:
                    # Check if the body is gzip compressed (PostHog uses compression=gzip-js)
                    body_str = None
                    if body.startswith(b'\x1f\x8b'):  # gzip magic number
                        # Decompress gzip data
                        try:
                            decompressed = gzip.decompress(body)
                            body_str = decompressed.decode('utf-8')
                        except Exception as e:
                            print(f"Failed to decompress gzip PostHog data: {e}")
                            # If decompression fails, skip user injection
                            body_str = None
                    else:
                        # Not compressed, decode as usual
                        body_str = body.decode('utf-8')
                    
                    if body_str:
                        # PostHog sends data in different formats, handle the most common ones
                        if body_str.startswith('data='):
                            # URL-encoded format: data={"batch":[...]}
                            from urllib.parse import unquote_plus
                            json_part = body_str[5:]  # Remove 'data=' prefix
                            json_data = json.loads(unquote_plus(json_part))
                        else:
                            # Direct JSON format
                            json_data = json.loads(body_str)
                        
                        # Get user ID from session
                        user_id = session.get('user_id')
                        user_email = session.get('email')
                        user_name = session.get('name')
                        
                        if user_id:
                            # Inject user properties into PostHog events
                            if 'batch' in json_data:
                                # Batch format (multiple events)
                                for event in json_data['batch']:
                                    if 'properties' not in event:
                                        event['properties'] = {}
                                    
                                    # Set distinct_id to user_id for proper user identification
                                    event['distinct_id'] = user_id
                                    
                                    # Add user properties
                                    event['properties']['user_id'] = user_id
                                    if user_email:
                                        event['properties']['user_email'] = user_email
                                    if user_name:
                                        event['properties']['user_name'] = user_name
                                    
                            elif 'distinct_id' in json_data or 'event' in json_data:
                                # Single event format
                                json_data['distinct_id'] = user_id
                                
                                if 'properties' not in json_data:
                                    json_data['properties'] = {}
                                
                                json_data['properties']['user_id'] = user_id
                                if user_email:
                                    json_data['properties']['user_email'] = user_email
                                if user_name:
                                    json_data['properties']['user_name'] = user_name
                        
                        # Convert back to the original format
                        if body_str.startswith('data='):
                            from urllib.parse import quote_plus
                            modified_body = f"data={quote_plus(json.dumps(json_data))}"
                            modified_body_bytes = modified_body.encode('utf-8')
                        else:
                            modified_body_bytes = json.dumps(json_data).encode('utf-8')
                        
                        # Re-compress if original was compressed
                        if body.startswith(b'\x1f\x8b'):
                            body = gzip.compress(modified_body_bytes)
                        else:
                            body = modified_body_bytes
                    
                except (json.JSONDecodeError, UnicodeDecodeError, KeyError, gzip.BadGzipFile) as e:
                    # If we can't parse the body, just forward it as-is
                    print(f"Could not parse PostHog request body for user injection: {e}")
                    pass
            
            # Prepare headers, excluding problematic ones
            headers = {
                key: value for key, value in request.headers.items()
                if key.lower() not in [
                    "host", "content-length", "connection", 
                    "upgrade", "proxy-connection", "te", "trailer",
                    "accept-encoding"  # Let httpx handle encoding
                ]
            }
            
            # Add User-Agent if not present
            if "user-agent" not in headers:
                headers["user-agent"] = "MedStudyAI-Proxy/1.0"
            
            # Update content-length if body was modified
            if body:
                headers["content-length"] = str(len(body))
            
            # Forward the request to PostHog
            response = await client.request(
                method=request.method,
                url=posthog_url,
                headers=headers,
                content=body,
                params=request.query_params,
                follow_redirects=True
            )
            
            # Get response content
            content = response.content
            
            # Prepare response headers, excluding problematic ones
            response_headers = {
                key: value for key, value in response.headers.items()
                if key.lower() not in [
                    "content-encoding", "transfer-encoding", "connection",
                    "upgrade", "proxy-connection", "te", "trailer"
                ]
            }
            
            # Set correct content-length
            response_headers["content-length"] = str(len(content))
            
            return Response(
                content=content,
                status_code=response.status_code,
                headers=response_headers
            )
            
    except httpx.TimeoutException:
        print(f"PostHog proxy timeout for {path}")
        raise HTTPException(status_code=504, detail="Analytics service timeout")
    except httpx.RequestError as e:
        print(f"PostHog proxy error for {path}: {str(e)}")
        raise HTTPException(status_code=502, detail="Analytics service unavailable")
    except Exception as e:
        print(f"PostHog proxy unexpected error for {path}: {str(e)}")
        raise HTTPException(status_code=500, detail="Analytics proxy error")

# Catch-all route for client-side routing (React Router)
@app.get("/{path:path}")
async def serve_static(path: str):
    print(f"Serving static file: {path}")
    try:
        # If it's an asset file (CSS, JS), serve it
        if path.startswith('assets/'):
            return FileResponse(os.path.join(static_folder, path))
        # For all other routes, serve index.html (let React Router handle it)
        else:
            return FileResponse(os.path.join(static_folder, 'index.html'))
    except Exception as e:
        print(f"Error serving static file {path}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to serve static file {path}: {str(e)}")
    
    