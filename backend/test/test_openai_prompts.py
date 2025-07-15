from dotenv import load_dotenv
from openai import OpenAI
import os
import json
import time

load_dotenv()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

summary_text = """
    # Rhabdomyolysis Study Guide

## Overview
Rhabdomyolysis (RM) is a serious medical condition characterized by the breakdown of skeletal muscle tissue, leading to symptoms and complications that can be both limb and life-threatening. This guide aims to outline critical knowledge surrounding rhabdomyolysis, from its etiology to management, while providing clinical correlates for better understanding.

---

## Page-by-Page Summary

### Page 1: Title
- **Topic:** Rhabdomyolysis
- **Presenter:** Janet Gregory, DO

### Page 2: Objectives
- **Recognize the clinical syndrome of rhabdomyolysis:** Understand the symptoms and physiological changes.
- **Describe complications of rhabdomyolysis:** Learn potential outcomes if not managed appropriately.
- **Identify potential etiologies of rhabdomyolysis:** Explore causes including trauma and drug use.
- **Outline the evaluation of a patient with rhabdomyolysis:** Know diagnostic tests and their significance.
- **Introduction to the management of rhabdomyolysis:** Discuss appropriate interventions and treatments.

### Page 3: Clinical Case Introduction
- **Case Study:** A 25-year-old man brought to the ED with severe agitation and confusion may suggest underlying substance use or psychological disorder, which could lead to rhabdomyolysis through violence or exertion.
- **Clinical signs:**
  - Severe agitation and tachycardia in confinement raise suspicion for an Agitated Delirium, potentially linked to "bath salts" or other stimulants associated with rhabdomyolysis.

### Page 4: What is Rhabdomyolysis?
- **Definition:** Dissolution of skeletal muscle leading to release of muscle cell contents.
- **Mechanisms of injury:** 
  - **Myoglobin leaks** into blood causing renal damage.
  - Release of:
    - Creatinine kinase (CK)
    - Lactate dehydrogenase
    - Electrolytes
- **Clinical triad of symptoms:**
  - **Muscle pain:** Due to cellular damage.
  - **Muscle weakness:** Associated with impaired muscle function.
  - **Dark urine:** Characteristic of myoglobinuria.

### Page 5: Pathophysiology Diagram
- Not applicable; this page should contain related figures demonstrating cells and processes involved in muscle breakdown and subsequent biochemical derangements.

### Page 6: Causes
- **Categories of causes:**
  - **Trauma:** Crush syndrome, prolonged immobilization.
  - **Exertional:** Overexertion, seizure episodes, stimulant intoxication.
  - **Temperature extremes:** Hyperthermia or hypothermia.
  - **Metabolic issues:** Various ionic deficiencies such as hypokalemia impacting muscular function.
  - **Muscle ischemia:** Resulting from arterial obstruction.
  - **Medications and toxins:** Highlighting specific agents (e.g., statins, alcohol, illicit drugs) that could lead to rhabdomyolysis.
  - **Infections and autoimmune disorders:** Viral infections and conditions affecting muscle health.

### Page 7: Complications
- **Primary complications include:**
  - **Electrolyte derangements:** Risk of hyperkalemia, hyponatremia impacting heart rhythms.
  - **Acute kidney injury (AKI):** Most concerning sequelae due to nephrotoxicity of myoglobin.
  - **Compartment syndrome:** Increased pressure leading to tissue necrosis.
  - **Disseminated intravascular coagulation (DIC):** Rare but severe coagulopathy.

### Page 8: Evaluation
- **Necessary evaluations:**
  - **Creatinine Kinase (CK):** Marker for muscle injury, levels >5x normal warrant concern.
  - **Complete Blood Count (CBC), Metabolic Panel (CMP):** Assessing renal function, electrolyte levels.
  - **Urinalysis (UA):** Screening for blood and myoglobin.
  - **Electrocardiogram (ECG):** To monitor for dysrhythmias, especially hypokalemic or hyperkalemic changes.

### Page 9: Treatment
- **Interventions include:**
  - **Address the root cause:** Stop medications or treat underlying pathology.
  - **IV Fluids:** Administer isotonic saline or lactated Ringer's to maintain urine output.
  - **Urinary alkalinization:** Strive to maintain urine pH >6.5 to prevent myoglobin precipitation in the kidneys.
  - **Renal replacement therapy:** Critical for severe cases with significant AKI.

### Page 10: Special Considerations
- **Pediatrics:** Younger populations are often prone to viral myositis.
- **Genetic predispositions:** Individuals with sickle cell trait at higher risk, particularly during dehydration and exertional stress.
- **HIV infections:** Instances of rhabdomyolysis have been reported during seroconversion phases.

### Page 12: References
- Ensure to reference high-quality sources such as StatPearls, UpToDate, and scientific journals for further readings.

---

## High-Yield Information
- **Recognizing symptoms** like muscle pain, weakness, and dark urine is crucial for quick identification.
- Knowledge of **complication profiles** can aid in prioritizing treatment options effectively.
- Understanding **key diagnostic values** (e.g., CK levels) assists in ruling in/out rhabdomyolysis swiftly.
- Awareness of drugs and **environmental factors** helps in preventive and therapeutic strategies.

### Key Terms
- **Myoglobinuria:** Presence of myoglobin in the urine indicating muscle damage.
- **Creatinine Kinase (CK):** Serum enzyme level monitoring for muscle integrity.
- **Compartment Syndrome:** Emergency requiring potential surgical intervention.

---

## Conclusion
Utilizing this guide will help solidify your understanding of rhabdomyolysis, providing a strong basis for clinical applications and enhancing readiness for examinations such as the USMLE and COMLEX. Always integrate knowledge with practical examples to facilitate recall and application in real-world scenarios.
    """



def gpt_summarize_transcript(text, stream=False):
    print(f"gpt_summarize_transcript called with stream={stream}")



    prompt = f"""Create a comprehensive, detailed study guide/summary from this transcript that covers ALL content thoroughly.

    CRITICAL REQUIREMENTS:
    - You MUST read and analyze the ENTIRE transcript from beginning to end, no matter how long it is
    - Do NOT skip any sections, pages, or content - process everything completely
    - Include information from EVERY single page, section, paragraph, and sentence of the transcript
    - Focus on high-yield information for USMLE, COMLEX, and medical school exams
    - Include ALL key concepts, clinical correlates, and important details mentioned throughout
    - Provide real-world examples and clinical applications
    - Make this as comprehensive and detailed as possible - leave nothing out
    - Structure the content logically with clear organization
    - If the transcript is very long, take your time to process it completely and thoroughly

    FORMAT REQUIREMENTS:
    - Use Markdown formatting throughout
    - Use headers (# for main sections, ## for subsections)
    - Use bold (**text**) for key terms and important concepts
    - Use italics (*text*) for emphasis and definitions
    - Use bulleted lists (-) for key points and examples
    - Use numbered lists (1.) for step-by-step processes
    - Include tables where appropriate for comparisons
    - Use blockquotes (>) for important clinical pearls

    IMPORTANT: This transcript contains {len(text)} characters. Please ensure you process every single character and include all details in your summary.

    Transcript:
    {text}
    """

    completion = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert medical educator and USMLE/COMLEX tutor with extensive experience creating comprehensive study materials. Your goal is to create the most thorough, detailed, and well-organized study guides possible. You excel at identifying high-yield content, explaining complex concepts clearly, and structuring information in ways that maximize learning and retention. Always double-check your responses for accuracy and completeness."},
            {"role": "user", "content": prompt},
        ],
        temperature=1.2,
        presence_penalty=0.6,
        stream=stream,
    )
    

    # Parse the response into lines
    text = completion.choices[0].message.content.strip()
    return text



def generate_quiz_questions(summary_text, previous_questions=None, num_questions=5, is_quiz_mode=True, model="gpt-4o-mini", stream=False):
    """Generate quiz questions from a summary text using OpenAI's API
    
    Args:
        summary_text: The text to generate questions from
        user_id: User ID for question hashing
        content_hash: Content hash for question set
        incorrect_question_ids: Optional list of IDs of questions answered incorrectly
        previous_questions: Optional list of previous questions for focused generation
        num_questions: Number of questions to generate (default: 5)
        stream: Whether to stream the response (default: False)
    
    Returns:
        tuple: (questions, question_hashes) or generator if streaming
    """
    
    try:
        print(f"is_quiz_mode: {is_quiz_mode}")
        
        if is_quiz_mode:
            max_completion_tokens = 10000
            quiz_schema = {
                "type": "object",
                "required": ["questions"],
                "additionalProperties": False,
                "properties": {
                    "questions": {
                        "type": "array",
                        "minItems": num_questions,
                        "maxItems": num_questions,
                        "items": {
                            "type": "object",
                            "required": ["id", "text", "options", "correctAnswer", "reason"],
                            "properties": {
                                "id":           {"type": "integer", "minimum": 1, "maximum": num_questions},
                                "text":         {"type": "string"},
                                "options": {
                                    "type": "array",
                                    "minItems": 4,
                                    "maxItems": 4,
                                    "items": {"type": "string"}
                                },
                                "correctAnswer": {"type": "integer", "minimum": 0, "maximum": 3},
                                "reason":       {"type": "string"}
                            },
                            "additionalProperties": False
                        }
                    }
                }
            }
            prompt = f'''
            Based on the following medical text summary, create {num_questions} VERY challenging USMLE clinical vignette style \
                multiple-choice questions to test the student's understanding. Make sure to include all the key concepts and information from the summary.
            
            Requirements:
            1. Clear, specific and challenging clinical vignette stems (about 400 characters).
            2. Question stems must be in the style of a USMLE clinical vignette 
            3. Include a thorough explanation (about 500 characters) for why the correct answer is right and why others are wrong. Do not include the answer index in the reason.
            4. Aim for clarity, clinical relevance, and high-yield facts

            Example question fromat:
            [
                {{
                    "id": 1,
                    "text": "A 34-year-old man presents to the emergency department with 5 days of worsening shortness of breath, orthopnea, and a nonproductive cough. He has no significant past medical history. Vitals show BP 110/70 mmHg, HR 105/min, and RR 22/min. Jugular venous distention is noted, and auscultation reveals bilateral crackles. ECG shows low-voltage QRS complexes. A chest x-ray demonstrates an enlarged cardiac silhouette. What is the most appropriate next step?",
                    "options": [
                        "A. Start loop diuretics",
                        "B. Order a transthoracic echocardiogram",
                        "C. Begin corticosteroid therapy",
                        "D. Perform emergent cardiac catheterization"
                    ],
                    "correctAnswer": 2,
                    "reason": "The patient presents with signs of acute heart failure and pericardial effusion (dyspnea, JVD, low-voltage ECG, enlarged cardiac silhouette). These findings raise concern for cardiac tamponade, which can be rapidly fatal. The most appropriate next step is a transthoracic echocardiogram to evaluate for pericardial fluid and assess for signs of tamponade physiology such as diastolic collapse of the right heart chambers."
                }},
                ...
            ]

            Summary:
            {summary_text}
            '''

            system_prompt = """
            You are an expert medical professor that creates 
            accurate, challenging USMLE clinical vignette style multiple choice questions. 
            Output **only** valid JSON exactly matching the schema below.
            """
        else:
            max_completion_tokens = 16000
            quiz_schema = {
                "type": "object",
                "required": ["questions"],
                "additionalProperties": False,
                "properties": {
                    "questions": {
                        "type": "array",
                        "minItems": num_questions,
                        "maxItems": num_questions,
                        "items": {
                            "type": "object",
                            "required": ["id", "text", "options", "correctAnswer", "reason"],
                            "properties": {
                                "id":           {"type": "integer", "minimum": 1, "maximum": num_questions},
                                "text":         {"type": "string"},
                                "options": {
                                    "type": "array",
                                    "minItems": 1,
                                    "maxItems": 1,
                                    "items": {"type": "string"}
                                },
                                "correctAnswer": {"type": "integer", "minimum": 0, "maximum": 0},
                                "reason":       {"type": "string"}
                            },
                            "additionalProperties": False
                        }
                    }
                }
            }
            prompt = f'''
            Based on the following medical text summary, create {num_questions}
            active‑recall flashcards that cover every key concept.

            Requirements:
            1. Clear, specific, and concise question stems for active recall flashcards (about 100 characters). Do not include the answer in the question stem or suggest there are multiple answers.
            2. Simple, direct active recall flashcard questions based on the summary.
            3. Include a thorough explanation (about 500 characters) for why the correct answer is right and why others are wrong. Do not include the answer index in the reason.
            4. Aim for clarity, clinical relevance, and high-yield facts
            5. Each flashcard must contain one clear fact.

            Example flashcard format:
            [
                {{
                    "id": 1,
                    "text": "Which cytokine is most critical for Th1 differentiation?",
                    "options": ["IL-12"],
                    "correctAnswer": 0,
                    "reason": "IL-12 is essential for naïve CD4+ T cells to differentiate into Th1 cells. It activates STAT4, a transcription factor that upregulates T-bet, the master regulator of Th1 lineage commitment. T-bet then promotes the production of IFN-γ, the key Th1 cytokine, which amplifies the Th1 response. In contrast, IL-4 promotes Th2 differentiation, IL-6 supports Th17 development, and IL-10 suppresses inflammatory responses, including Th1 activity."
                }},
                ...
            ]

            Summary:
            {summary_text}
            '''

            system_prompt = """
            You are an expert medical professor that creates 
            accurate, active recall flashcard questions. 
            Output **only** valid JSON exactly matching the schema below.
            """
        
        print(f"Using model: {model} for quiz generation USMLE mode: {is_quiz_mode} with max completion tokens: {max_completion_tokens}")
        gpt_time_start = time.time()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        if previous_questions and len(previous_questions) > 0:
            messages.append({"role": "user", "content": f"Generate {num_questions} new questions that are cover entirely different topics from the questions below. \n\n{json.dumps(previous_questions)}"})

        # print("messages")
        # print(messages)

        response = openai_client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "quiz_questions",
                    "strict": True,
                    "schema": quiz_schema
                }
            },
            temperature=0.2,
            presence_penalty=0.0,
            max_completion_tokens=max_completion_tokens,
            top_p=0.9,
            frequency_penalty=0.2,
            stream=stream
        )

        if stream:
            # For streaming, return the response object directly
            return response
        
        # Non-streaming handling remains the same
        print(f"Completion tokens used: {response.usage.completion_tokens}")
        gpt_time_end = time.time()
        print(f"GPT time: {gpt_time_end - gpt_time_start} seconds")

        response_text = response.choices[0].message.content.strip()
        response_json = json.loads(response_text)
        questions = response_json["questions"]
        
        print(f"Type of questions: {type(questions)}")
        if not isinstance(questions, list) or not questions:
            raise ValueError("Response is not a list or is empty.")
    
        print(f"Number of questions: {len(questions)}")
        print(questions[0].keys())
        question_texts = []
        for question in questions:
            print(question["id"])
            print(question["text"])
            # print(question["options"])
            # print(question["correctAnswer"])
            # print(question["reason"])
            print("--------------------------------")
            question_texts.append(question["text"])
            

        # print(question_texts)
        # print(previous_questions)
        return questions

    except Exception as e:
        print(f"Error generating quiz questions: {e}")
        if stream:
            return None
        return []


def find_complete_object(text, start_pos=0):
    """Find the next complete JSON object in the text starting from start_pos.
    Returns (start_index, end_index) of the complete object, or None if no complete object is found."""
    # Find the start of an object
    bracket_stack = []
    in_string = False
    escape_next = False
    object_start = None
    
    # Skip until we find a '{' that starts a question object
    i = start_pos
    while i < len(text) and not object_start:
        if text[i:].startswith('{"id"'):
            object_start = i
            bracket_stack.append('{')
        i += 1
        
    if not object_start:
        return None
        
    # Parse from the start of the question object
    for i in range(object_start + 1, len(text)):
        char = text[i]
        
        # Handle string literals
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        
        if in_string:
            escape_next = char == '\\'
            continue
            
        # Handle brackets outside strings
        if char in '{[':
            bracket_stack.append(char)
        elif char in '}]':
            if not bracket_stack:
                continue  # Ignore closing brackets without matching open
            
            # Check matching brackets
            open_char = bracket_stack[-1]
            if (open_char == '{' and char == '}') or (open_char == '[' and char == ']'):
                bracket_stack.pop()
                if not bracket_stack:  # All brackets matched
                    return (object_start, i + 1)
        
    return None

def process_streaming_questions(stream):
    """Process a streaming response from OpenAI and extract questions as they arrive.
    
    Args:
        stream: OpenAI streaming response object
        
    Returns:
        list: List of processed question objects
    """
    accumulated_json = ""
    questions_found = set()
    last_processed_pos = 0
    array_started = False
    processed_questions = []
    
    for chunk in stream:
        if chunk.choices[0].delta.content:
            accumulated_json += chunk.choices[0].delta.content
            
            # Look for the start of the questions array if we haven't found it yet
            if not array_started and '"questions":' in accumulated_json:
                array_start_pos = accumulated_json.index('"questions":') + len('"questions":')
                # Skip any whitespace and the opening bracket
                while array_start_pos < len(accumulated_json) and accumulated_json[array_start_pos] not in '[{':
                    array_start_pos += 1
                if array_start_pos < len(accumulated_json) and accumulated_json[array_start_pos] == '[':
                    array_started = True
                    last_processed_pos = array_start_pos + 1
            
            # Only look for objects if we've found the start of the array
            if array_started:
                # Process all complete objects in the accumulated text
                while (result := find_complete_object(accumulated_json, last_processed_pos)):
                    start_pos, end_pos = result
                    object_text = accumulated_json[start_pos:end_pos]
                    
                    try:
                        # Try to parse the object
                        data = json.loads(object_text)
                        
                        # If it's a question object
                        if isinstance(data, dict) and all(key in data for key in ["id", "text", "options", "correctAnswer", "reason"]):
                            question_id = data["id"]
                            if question_id not in questions_found:
                                print(f"\nQuestion {question_id}:")
                                print(f"Q: {data['text']}")
                                print(f"A: {data['options'][data['correctAnswer']]}")
                                print(f"Explanation: {data['reason']}")
                                print("-" * 50)
                                questions_found.add(question_id)
                                processed_questions.append(data)
                    except json.JSONDecodeError:
                        pass
                        
                    last_processed_pos = end_pos + 1  # Skip the comma after the object
    
    return processed_questions

if __name__ == "__main__":
    # print(gpt_summarize_transcript(summary_text))
    previous_questions = None
    # previous_questions = ['What is the primary definition of rhabdomyolysis?', 'What are the three classic symptoms of rhabdomyolysis?', 'Which electrolyte imbalance is most concerning in rhabdomyolysis?', 'What is a common cause of rhabdomyolysis related to exercise?', 'What diagnostic test is primarily used to assess muscle injury in rhabdomyolysis?', 'What complication can arise from severe rhabdomyolysis affecting kidney function?', 'Which management strategy is crucial for treating rhabdomyolysis?', 'What urinary pH target helps prevent kidney damage in rhabdomyolysis?', 'What role does myoglobin play in rhabdomyolysis?', 'What type of syndrome can develop due to increased pressure from swelling in muscles affected by rhabdomyolysis?', 'Which demographic group is at higher risk for viral myositis related to rhabdomyolysis?', 'What substance use disorder could be linked with agitation leading to rhabdomyolysis?', 'What metabolic issue could contribute to muscle dysfunction in patients with rhabdomyolysis?', 'Which laboratory test would be used for screening blood presence indicative of muscle injury?', 'What should be done first when treating a patient with suspected rhabdomyolysis?', 'What condition could result from prolonged immobilization leading to muscle breakdown?', 'How does lactate dehydrogenase (LDH) relate to muscle injury assessment?', 'Which condition may trigger disseminated intravascular coagulation (DIC) linked with severe cases of rhabdomyolysis?', 'Why should an ECG be performed on patients suspected of having electrolyte imbalances due to rhabdomyolysis?', 'How do environmental factors contribute to the risk of developing rhabdomyolysis?']
    # questions = generate_quiz_questions(summary_text, previous_questions=previous_questions, num_questions=20, is_quiz_mode=False, model="gpt-4o-mini")
    # print(questions)
    stream = generate_quiz_questions(summary_text, previous_questions=previous_questions, num_questions=20, is_quiz_mode=False, model="gpt-4o-mini", stream=True)
    if stream:
        questions = process_streaming_questions(stream)
    

