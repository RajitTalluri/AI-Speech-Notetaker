import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "phi3"

def refine(raw_text_blocks):
    """
    Takes a list of raw transcript blocks and returns cleaned notes.
    """
    raw_text = "\n".join(raw_text_blocks)
    prompt = f"""
Act as a note taking assistant.
You receive raw transcripts from audio recordings and you will improve the clarity, grammar, and conciseness of the notes.

Rules:
- Remove filler words (e.g., "um", "uh", "like").
- Seperate phrases into bullet points.
- Keep technical accuracy.
- Combine related ideas
- Do not add information

Transcript:
\"\"\"
{raw_text}
\"\"\"
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False # false waits for full response
        },
        timeout=300 # in case of hanging 
    )

    response.raise_for_status() # error raise
    return response.json()["response"]
