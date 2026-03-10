import requests
import logging

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:7b" 

def refine(raw_text_blocks):
    """
    Takes a list of raw transcript blocks and returns cleaned notes.
    """
    logger.info(f"refine() called with {len(raw_text_blocks)} text blocks")
    raw_text = "\n".join(raw_text_blocks)
    logger.info(f"Combined raw text size: {len(raw_text)} characters")
    
    prompt = f"""
Act as a note taking assistant.
You receive raw transcripts from audio recordings and you improve the clarity, grammar, and conciseness of the notes.
The recording is for a project presentation.

Rules:
- Remove filler/irrelevant words ("um", "uh", "like", etc.)
- Seperate phrases into bullet points
- Keep technical accuracy
- Combine related ideas
- Do not add information

Transcript:
\"\"\"
{raw_text}
\"\"\"
"""
    logger.debug(f"Prompt created | Size: {len(prompt)} characters")
    logger.info(f"Sending request to Ollama API: {OLLAMA_URL} with model: {MODEL}")

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False # false waits for full response
            },
            timeout=300 # in case of hanging 
        )
        logger.info(f"Ollama API response received | Status code: {response.status_code}")
        response.raise_for_status() # error raise
        result = response.json()["response"]
        logger.info(f"AI cleanup completed successfully | Result size: {len(result)} characters")
        return result
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling Ollama API: {e}", exc_info=True)
        raise

