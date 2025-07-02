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

def generate_quiz_questions(summary_text):
    """Generate quiz questions from a summary text using OpenAI's API"""
    
    quiz_schema = {
        "type": "object",
        "required": ["questions"],
        "additionalProperties": False,
        "properties": {
            "questions": {
                "type": "array",
                "minItems": 5,
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "required": ["id", "questionStem", "answerChoices", "correctAnswer", "reason"],
                    "properties": {
                        "id":           {"type": "integer", "minimum": 1, "maximum": 5},
                        "questionStem":         {"type": "string"},
                        "answerChoices": {
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

    previous_questions = []
    incorrect_question_ids = []

    is_questions = previous_questions is not None and incorrect_question_ids is not None

    incorrect_questions = []
    correct_questions = []
    if is_questions:
        incorrect_questions = [q['text'] for q in previous_questions if q['id'] in incorrect_question_ids]
        correct_questions = [q['text'] for q in previous_questions if q['id'] not in incorrect_question_ids]

    correct_questions = ["A 40-year-old female presents to the emergency department following an intense kickboxing class. She reports severe generalized muscle pain, weakness, and dark brown urine that began hours after the class. Laboratory tests reveal a significantly elevated creatine kinase level. Which of the following pathophysiological mechanisms is primarily responsible for this patient's symptoms?"]
    incorrect_questions = ["A 28-year-old male marathon runner is admitted after experiencing debilitating muscle cramps and dark red urine during a long-distance race. His laboratory workup reveals very high creatine kinase levels and hyperkalemia. Given his clinical status, which of the following should be performed as the most critical first step in management?"]

    previous_questions_text = ""
    if len(incorrect_questions) > 0:
        previous_questions_text += f"The user previously answered the following questions INCORRECTLY and should be tested on these topics as well as others mentioned in the summary:\n{json.dumps(incorrect_questions)}\n"
    if len(correct_questions) > 0:
        previous_questions_text += f"The user previously answered the following questions CORRECTLY and should be tested on different topics mentioned in the summary:\n{json.dumps(correct_questions)}\n"

    prompt = f"""
    Based on the following medical text summary, create 5 VERY challenging USMLE clinical vignette style \
        multiple-choice questions to test the student's understanding. Make sure to include all the key concepts and information from the summary.
    
    {previous_questions_text}

    For each question:
    1. A clear, specific and challenging clinical vignette stem.
    2. Be in the style of a USMLE clinical vignette (Example clinical vignette stem: "A 62-year-old man presents to the emergency department with shortness of breath and chest discomfort that began two hours ago while he was watching television. He describes the discomfort as a vague pressure in the center of his chest, without radiation. He denies any nausea or diaphoresis. He has a history of hypertension, type 2 diabetes mellitus, and hyperlipidemia. He is a former smoker (40 pack-years, quit 5 years ago). On examination, his blood pressure is 146/88 mmHg, heart rate is 94/min, respiratory rate is 20/min, and oxygen saturation is 95% on room air. Cardiac auscultation reveals normal S1 and S2 without murmurs. Lungs are clear to auscultation bilaterally. There is no jugular venous distension or peripheral edema. ECG reveals normal sinus rhythm with 2 mm ST-segment depressions in leads V4–V6. Cardiac biomarkers are pending. Which of the following is the most appropriate next step in management?")
    3. Include a thorough explanation for why the correct answer is right and why others are wrong (Dont include the answer index in the reason)
    
    Summary:
    {summary_text}
    """

    system_prompt = """
    You are an expert medical professor that creates 
    accurate, challenging USMLE clinical vignette style multiple choice questions. 
    Generate ONLY valid JSON matching the provided schema.
    """
            
    gpt_time_start = time.time()
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "quiz_questions",
                "strict": True,
                "schema": quiz_schema
            }
        },
        temperature=0.9,
        presence_penalty=0.6,
        max_completion_tokens=1200,
        top_p=0.9,
        frequency_penalty=0.25,
    )
    gpt_time_end = time.time()
    print(f"GPT time: {gpt_time_end - gpt_time_start} seconds")

    response_text = response.choices[0].message.content.strip()
    
    response_json = json.loads(response_text)
    questions = response_json["questions"]  # Extract the questions array from the response
    print(f"Type of questions: {type(questions)}")
    if not isinstance(questions, list) or not questions:
      raise ValueError("Response is not a list or is empty.")
    
    print(f"Number of questions: {len(questions)}")
    print(questions[0].keys())
    for question in questions:
        print("--------------------------------")
        print(question["id"])
        print(question["questionStem"])
        print(question["answerChoices"])
        print(question["correctAnswer"])
        print(question["reason"])


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

if __name__ == "__main__":
    # print(gpt_summarize_transcript(summary_text))
    generate_quiz_questions(summary_text)
    

