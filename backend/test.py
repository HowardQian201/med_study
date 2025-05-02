from openai_apikey import key as OPENAI_API_KEY
from openai import OpenAI
from text import text


client = OpenAI(api_key=OPENAI_API_KEY)

def prompt_gpt(text):
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


if __name__ == "__main__":
    gpt_response = prompt_gpt(text)
    print(gpt_response)
