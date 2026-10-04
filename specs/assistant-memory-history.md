# Assistant history and long-term memory

## Local conversation history

- The assistant appends each user message, assistant response, and tool action to `data/assistant_history.log` as one JSON object per line (JSON Lines).
- A browser-generated conversation ID lets the assistant restore and continue that conversation after a reload. The model receives the latest 12 user/assistant messages; the full local transcript remains available to the history view.
- Use **Clear history** in the assistant panel to truncate the conversation and action log. This does not delete tasks or saved memories.
- The log is ignored by Git. It is local plaintext, so do not send passwords, credentials, or other secrets to the assistant. Chat prompts are sent to the configured Groq service for processing.

## Saved memories

- Memories are explicit: the assistant saves a fact, preference, or goal only when asked to remember it.
- Memory contents are stored in `data/assistant_memory.db`, separate from the task database, and supplied to the assistant on later requests. The assistant can list, search, and forget individual memories.
- The memory database is ignored by Git. Clearing chat history leaves memories intact. Ask the assistant to forget a memory to remove it.
- Memory content is limited to 500 characters; credentials and common sensitive identifiers are rejected.

## Task execution boundary

- The assistant can read and change DAYMARK's local task database, suggest available slots, and summarize incomplete overdue, due-today, and next-seven-day tasks when asked.
- Deleting a task requires the assistant to identify its ID and the user to reply `Confirm delete <task_id>`.
- DAYMARK does not run a background worker or external actions while the app is stopped. The assistant must not claim to send reminders or execute work in the background.
