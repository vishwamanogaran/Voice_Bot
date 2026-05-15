# Backend/workers.py

import asyncio

from audio_pipeline import AudioPipeline


# =========================================================
# AUDIO PIPELINE
# =========================================================
pipeline = AudioPipeline(
    upload_folder="../uploads"
)


# =========================================================
# SESSION AUDIO WORKER
# =========================================================
async def audio_worker(session):

    print(
        f"Audio worker started: "
        f"{session.session_id}"
    )

    while True:

        try:

            # =============================================
            # GET AUDIO CHUNK
            # =============================================
            audio_bytes = await session.audio_queue.get()

            # =============================================
            # PROCESS AUDIO
            # =============================================
            response = await pipeline.process_audio_chunk(

                session,

                audio_bytes
            )

            # =============================================
            # SEND RESPONSE
            # =============================================
            if response:

                await session.response_queue.put(
                    response
                )

        except asyncio.CancelledError:

            print(
                f"Worker cancelled: "
                f"{session.session_id}"
            )

            break

        except Exception as e:

            print(
                f"Audio Worker Error "
                f"({session.session_id}): {e}"
            )