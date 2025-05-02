from openai_apikey import key as OPENAI_API_KEY
from openai import OpenAI
import whisper
import psutil
import subprocess
import platform


client = OpenAI(api_key=OPENAI_API_KEY)
model = whisper.load_model("small")

def gpt_summarize_transcript(text):
    prompt = f"Provide me with detailed and concise notes on this transcript, and include relevant headers for each topic. Be sure to include the mentioned clinical correlates. Transcript:{text}"

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful teaching assistant \
             (TA) for US medical school. You are extremely knowledgable and \
             want your students to succeed. You also double check your responses \
             for accuracy."},
            {"role": "user", "content": prompt},
        ],
    )

    # Parse the response into lines
    text = completion.choices[0].message.content.strip()
    return text
    

def set_process_priority():
    """Configure process priority based on OS"""
    current_process = psutil.Process()
    try:
        if platform.system() == 'Windows':
            current_process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            current_process.nice(10)  # Unix-like systems
    except:
        print("Could not set process priority")

def check_memory():
    """Check if system has enough memory"""
    if psutil.virtual_memory().percent > 90:
        raise Exception("Memory usage too high")

def save_uploaded_file(file, input_path):
    """Save uploaded file and return total bytes"""
    total_bytes = 0
    chunk_size = 1024 * 1024  # 1MB chunks
    
    with open(input_path, 'wb') as f:
        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                break
            check_memory()
            f.write(chunk)
            total_bytes += len(chunk)
            if total_bytes % (100 * 1024 * 1024) == 0:
                print(f"Received {total_bytes / (1024*1024):.1f} MB")
    
    return total_bytes


def process_audio(input_path, output_path):
    """Single-pass audio extraction and normalization"""
    ffmpeg_command = [
        'ffmpeg', '-y',
        '-f', 'mp4',
        '-i', str(input_path),
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        # Combine filters in one pass
        '-filter:a', 'volume=4.0,loudnorm=I=-16:LRA=11:TP=-1.5,highpass=f=50,lowpass=f=8000',
        '-f', 'wav',
        str(output_path)
    ]
    return subprocess.run(ffmpeg_command, capture_output=True, text=True)


def transcribe_audio(audio_path):
    """Transcribe audio using Whisper"""
    result = model.transcribe(
        str(audio_path),
        verbose=True,
        language='en',
        task='transcribe',
        condition_on_previous_text=True,
        temperature=0.0,
        best_of=1
    )
    
    transcription = result.get("text", "").strip()
    return transcription