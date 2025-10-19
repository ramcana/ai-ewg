
All-in-One n8n Workflow (Local) — Quick Setup
=============================================

This workflow scans a local folder for .mp4 videos, transcribes them with Whisper,
derives summary + key takeaway + segmented Q&A, builds JSON-LD and renders a static HTML page.

1) Environment variables (set in n8n or docker-compose):
   NN_INBOX= D:\newsroom\inbox\videos
   NN_TR_OUT= D:\newsroom\outputs\assets\transcripts
   NN_PAGES= D:\newsroom\outputs\pages
   NN_PUBLIC_BASE_URL= http://localhost
   NN_DEFAULT_HOST_NAME= The News Forum Host
   NN_DEFAULT_HOST_URL= https://www.thenewsforum.ca/hosts/default

   # Whisper command and model (ensure whisper is installed and in PATH)
   WHISPER_CMD= whisper
   WHISPER_MODEL= medium

2) Filename convention (used to auto-derive metadata):
   Show_EpisodeId_YYYY-MM-DD_Topic-Words.mp4
   Example: MyGeneration_S02E07_2025-10-16_AI-in-Industry.mp4

3) Outputs:
   - Transcripts (.txt, .vtt): in NN_TR_OUT
   - Static page: NN_PAGES/{show-slug}/{episodeId}-{topic-slug}/index.html

4) Notes:
   - The summary/Q&A step is heuristic (no LLM). You can swap it with an LLM node.
   - For Linux/macOS, replace the Powershell list command in the "List New Videos" node with:
       bash -lc "find '{ $env.NN_INBOX || "/data/inbox/videos" }' -type f -name '*.mp4'"
   - Ensure the folders exist and n8n has write permissions.
