# n8n Architecture Explained (Plain English)

## The Big Picture

Think of your setup like a restaurant:
- **n8n** = The waiter (takes orders, coordinates, reports back)
- **Python Server** = The kitchen (does the actual cooking/processing)
- **Workflows** = The menu (lists what can be ordered)

---

## Part 1: How n8n Connects to Your Python Server

### 1. **Your Python Server (The Kitchen)**

You have a **FastAPI server** running on your computer at:
```
http://localhost:8000
```

This server exposes "endpoints" (like a menu of services):
- `/health` - Check if server is running
- `/episodes/process` - Process a video
- `/episodes/{episode_id}` - Get status of a video
- `/status` - Get overall statistics

**How to start it:**
```bash
# Start the server (like opening the kitchen)
python -m src.api.server
```

It listens on port 8000 and waits for requests.

---

### 2. **n8n (The Waiter)**

n8n runs separately, usually in Docker at:
```
http://localhost:5678
```

When you click "Execute Workflow" in n8n, it acts like a waiter taking an order:
1. Collects the information (which video, what settings)
2. Makes an HTTP request to your Python server
3. Waits for the response
4. Shows you the results

**The Connection:**
```
n8n (localhost:5678)
    ↓
    HTTP Request
    ↓
Python Server (localhost:8000)
    ↓
    Processes Video
    ↓
    Returns Result
    ↓
n8n shows result to you
```

**Special Note:** When n8n runs in Docker, it can't use "localhost" to reach your computer. Instead, it uses:
```
http://host.docker.internal:8000
```
This is Docker's way of saying "the host computer" (your machine).

---

## Part 2: How n8n Workflows Are Created

### **What is a Workflow?**

A workflow is a visual diagram made of **nodes** (boxes) connected by **lines**. Think of it like a flowchart or assembly line.

### **The Workflow JSON File**

When you design a workflow in n8n's UI, it saves it as a JSON file like:
```
n8n_workflows/configurable_processing_v2.json
```

This JSON file contains:
1. **All the nodes** (boxes in the diagram)
2. **How they're connected** (arrows between boxes)
3. **What each node does** (the settings/parameters)

---

## Part 3: How Nodes Work

### **Example: Your Video Processing Workflow**

Let's walk through your actual workflow step-by-step:

#### **Node 1: Manual Trigger**
```
[👆 Click Me]
```
- **What it does**: Starts the workflow when you click "Execute"
- **Type**: Manual trigger
- **Output**: Triggers the next node

#### **Node 2: Set Configuration**
```
[⚙️ Set Config]
```
- **What it does**: Sets up the parameters:
  - `folder_path`: Where videos are
  - `target_stage`: How far to process (e.g., "rendered")
  - `force_reprocess`: Whether to redo existing videos
- **Type**: Set node (assigns variables)
- **Output**: Configuration data

#### **Node 3: Prepare Episodes**
```
[📋 JavaScript Code]
```
- **What it does**: Runs JavaScript code to:
  - List all video files in the folder
  - Generate episode IDs
  - Create data for each video
- **Type**: Code node
- **Output**: Array of episodes to process

#### **Node 4: Check Episode Status**
```
[🔍 HTTP Request]
```
- **What it does**: For EACH video:
  - Makes HTTP GET request to your Python server
  - URL: `http://host.docker.internal:8000/episodes/{episode_id}`
  - Asks: "What's the current status of this video?"
- **Type**: HTTP Request node
- **Output**: Current stage (e.g., "transcribed")

#### **Node 5: Prepare for Processing**
```
[🧮 JavaScript Code]
```
- **What it does**: Compares current stage vs target stage
  - If current = "transcribed" and target = "rendered"
  - Sets `needs_processing = true`
- **Type**: Code node
- **Output**: Decision on whether to process

#### **Node 6: Filter: Needs Processing**
```
[🚦 If/Else]
```
- **What it does**: Checks `needs_processing` flag
  - If TRUE → Send to next node
  - If FALSE → Skip (already processed)
- **Type**: If node
- **Output**: Only videos that need processing

#### **Node 7: Process Episode** ⭐
```
[🎬 HTTP Request - THE MAIN WORK]
```
- **What it does**: Makes HTTP POST request:
  ```
  POST http://host.docker.internal:8000/episodes/process
  Body: {
    "episode_id": "newsroom-2024-bb580",
    "target_stage": "rendered",
    "force_reprocess": true
  }
  ```
- **Timeout**: 30 minutes (because AI processing is slow)
- **Your Python server**: 
  - Receives this request
  - Starts processing the video:
    1. Extract audio
    2. Transcribe with Whisper
    3. AI enrichment with Ollama
    4. Generate HTML
  - Returns result when done
- **Type**: HTTP Request node
- **Output**: Processing result (success/failure)

#### **Node 8: Log Processing Result**
```
[📊 JavaScript Code]
```
- **What it does**: Formats the result nicely
  - Extracts: success, duration, stage, errors
- **Type**: Code node
- **Output**: Formatted result

#### **Node 9: Final Summary**
```
[📈 JavaScript Code]
```
- **What it does**: Combines all results:
  - How many succeeded?
  - How many failed?
  - Average processing time?
- **Type**: Code node
- **Output**: Summary report

---

## Part 4: The Connection Flow (Detailed)

### **When You Click "Execute Workflow":**

```
1. n8n: "Starting workflow..."
   └─> Node 1: Manual Trigger fires

2. n8n: "Running Set Configuration node..."
   └─> Sets: folder_path, target_stage, force_reprocess

3. n8n: "Running Prepare Episodes node..."
   └─> JavaScript creates list: [BB580.mp4, CI166.mp4, ...]

4. For EACH video file:
   
   n8n: "Checking status of BB580.mp4..."
   ├─> Makes GET request to Python server
   ├─> GET http://localhost:8000/episodes/newsroom-2024-bb580
   └─> Python server responds: {"stage": "transcribed"}

5. n8n: "Determining if processing needed..."
   └─> JavaScript: current="transcribed", target="rendered" → needs_processing=true

6. n8n: "Filtering..."
   └─> If node: needs_processing=true → PASS

7. n8n: "Processing BB580.mp4..." ⭐ THE BIG ONE
   ├─> Makes POST request to Python server
   ├─> POST http://localhost:8000/episodes/process
   ├─> Body: {"episode_id": "...", "target_stage": "rendered"}
   │
   ├─> Python server receives request
   ├─> Python: "Starting processing..."
   ├─> Python: "Loading video..."
   ├─> Python: "Extracting audio..."
   ├─> Python: "Transcribing with Whisper..." (5-7 min)
   ├─> Python: "AI enrichment with Ollama..." (8-12 min)
   ├─> Python: "Generating HTML..."
   ├─> Python: "Done! Sending response..."
   │
   └─> n8n receives response: {"success": true, "duration": 649}

8. n8n: "Logging result..."
   └─> JavaScript formats result

9. n8n: "Creating final summary..."
   └─> JavaScript: "1 video processed, 100% success, avg 10.8 min"

10. n8n: "Workflow complete!" ✅
```

---

## Part 5: How to Create/Modify Workflows

### **Option 1: Use n8n's Visual Editor (Easy)**

1. Open n8n: `http://localhost:5678`
2. Click "Workflows" → "Add Workflow"
3. Drag nodes from the left panel:
   - Triggers (Manual, Schedule, Webhook)
   - Actions (HTTP Request, Code, Set)
   - Logic (If, Switch, Merge)
4. Connect nodes by dragging arrows between them
5. Click each node to configure its settings
6. Click "Save"
7. Export: Click "..." menu → "Download" → Saves JSON file

### **Option 2: Edit JSON Directly (Advanced)**

The JSON structure:
```json
{
  "name": "My Workflow",
  "nodes": [
    {
      "id": "node-1",
      "name": "Manual Trigger",
      "type": "n8n-nodes-base.manualTrigger",
      "parameters": {},
      "position": [240, 300]
    },
    {
      "id": "node-2",
      "name": "HTTP Request",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "POST",
        "url": "http://host.docker.internal:8000/episodes/process",
        "jsonBody": "...",
        "options": {"timeout": 1800000}
      },
      "position": [450, 300]
    }
  ],
  "connections": {
    "Manual Trigger": {
      "main": [[{"node": "HTTP Request", "index": 0}]]
    }
  }
}
```

**What each part means:**
- **nodes**: Array of all the boxes in your workflow
  - Each has: id, name, type, parameters, position (x,y coordinates)
- **connections**: How nodes are linked
  - Format: `{"From Node": {"main": [[{"node": "To Node"}]]}}`
- **parameters**: Settings for each node
  - HTTP Request: URL, method, headers, body, timeout
  - Code: JavaScript code to execute
  - If: Condition to check

---

## Part 6: Common Node Types

### **1. Trigger Nodes (Start the workflow)**
- **Manual Trigger**: Click to start
- **Schedule**: Run automatically (e.g., every hour)
- **Webhook**: Triggered by external HTTP request

### **2. Action Nodes (Do stuff)**
- **HTTP Request**: Call APIs, talk to your Python server
- **Code**: Run custom JavaScript/Python
- **Set**: Create/modify variables
- **Read/Write Files**: Handle files on disk

### **3. Logic Nodes (Make decisions)**
- **If**: Branch based on condition
- **Switch**: Multiple branches
- **Merge**: Combine multiple paths
- **Loop**: Repeat for each item

### **4. Data Nodes (Process data)**
- **Item Lists**: Work with arrays
- **Transform**: Modify data structure
- **Filter**: Remove unwanted items

---

## Part 7: Your Current Setup

### **Files:**
```
n8n_workflows/
├── configurable_processing_v2.json  ← Your main workflow
├── folder_based_processing.json
├── batch_processing.json
└── ...

src/api/
├── server.py      ← Starts Python FastAPI server
├── endpoints.py   ← Defines /episodes/process, /health, etc.
└── models.py      ← Request/response formats
```

### **Ports:**
- **n8n**: `http://localhost:5678` (n8n interface)
- **Python API**: `http://localhost:8000` (your processing server)
- **From n8n in Docker**: `http://host.docker.internal:8000`

### **How They Talk:**
```
YOU (browser)
  ↓ http://localhost:5678
n8n (Docker container)
  ↓ http://host.docker.internal:8000
Python Server (your computer)
  ↓ (runs pipeline)
Ollama (localhost:11434)
Whisper (local model)
  ↓
Results saved to disk
  ↓
n8n shows you the results
```

---

## Part 8: Quick Start Guide

### **Start Everything:**
```bash
# 1. Start Python server
cd d:\n8n\TNF-Transcripts
venv\Scripts\activate
python -m src.api.server

# 2. Start Ollama (if not running)
ollama serve

# 3. Start n8n (already running in Docker)
# Just open browser: http://localhost:5678
```

### **Run a Workflow:**
1. Open n8n: `http://localhost:5678`
2. Open workflow: "Configurable Video Processing v2"
3. Set parameters in "Set Configuration" node
4. Click "Execute Workflow"
5. Watch the nodes light up as they process
6. See results in "Final Summary" node

### **Import a Workflow:**
1. n8n → "Workflows" → "Add Workflow"
2. Click "..." menu → "Import from File"
3. Select: `n8n_workflows/configurable_processing_v2.json`
4. Click "Save"

---

## Summary

**Simple Answer:**
- **n8n** = Visual automation tool that runs workflows
- **Python Server** = Your processing engine (FastAPI)
- **Workflow** = JSON file describing nodes and connections
- **HTTP Requests** = How n8n talks to your Python server

**The Magic:**
When you click "Execute" in n8n, it makes HTTP requests to your Python server's `/episodes/process` endpoint, which does all the heavy lifting (Whisper, Ollama, HTML generation), then n8n displays the results!

---

## Troubleshooting

**Problem**: n8n can't connect to Python server

**Solutions**:
- ✅ Check Python server is running: `curl http://localhost:8000/health`
- ✅ In n8n Docker, use `host.docker.internal:8000` not `localhost:8000`
- ✅ Check firewall allows port 8000

**Problem**: Workflow timeout

**Solutions**:
- ✅ Increase timeout in HTTP Request node (currently 30 min)
- ✅ Check Python server logs: `logs/pipeline.log`

**Problem**: Can't see workflows

**Solutions**:
- ✅ Import from JSON: n8n → Import → Select workflow file
- ✅ Check file exists: `n8n_workflows/*.json`

---

## Next Steps

Want to customize? Here's what you can do:
1. **Add nodes**: Drag from left panel in n8n
2. **Change settings**: Click node → Edit parameters
3. **Add error handling**: Use "On Error" workflow setting
4. **Schedule automatic runs**: Use Schedule Trigger instead of Manual
5. **Send notifications**: Add Email/Slack nodes

That's it! You now understand the complete architecture. 🎉
