# Backend/llm_engine.py

import httpx


# =========================================================
# OLLAMA CONFIG
# =========================================================
OLLAMA_URL = "http://localhost:11434/api/generate"

MODEL_NAME = "llama3.1:latest"


# =========================================================
# ASK LLM
# =========================================================
async def ask_llama(prompt, timeout_s: float = 120):

    try:

        async with httpx.AsyncClient(
            timeout=timeout_s
        ) as client:

            response = await client.post(

                OLLAMA_URL,

                json={

                    "model": MODEL_NAME,

                    "prompt": prompt,

                    "stream": False,

                    "options": {

                        "temperature": 0.8,
                    }
                }
            )

        # =================================================
        # STATUS CHECK
        # =================================================
        print("LLM response received")
        
        if response.status_code != 200:

            print(
                f"Ollama Error Status: "
                f"{response.status_code}"
            )

            return (
                "Sorry, I am having trouble "
                "responding right now."
            )

        # =================================================
        # JSON RESPONSE
        # =================================================
        data = response.json()

        ai_response = data.get(
            "response",
            ""
        ).strip()

        # =================================================
        # EMPTY RESPONSE CHECK
        # =================================================
        if not ai_response:

            return (
                "Sorry, I could not generate "
                "a response."
            )

        return ai_response

    except Exception as e:

        print("LLM Error:", e)

        return (
            "Sorry, I am facing a technical issue "
            "right now."
        )
