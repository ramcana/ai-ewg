# Episode Naming & Organization System

## 📋 Overview

The naming system provides consistent episode identification and folder organization based on AI-extracted metadata.

## 🎯 Features

1. **AI-Powered Naming** - Uses show name and episode number from enrichment
2. **Organized Folders** - Groups episodes by show and year
3. **Configurable Templates** - Customize naming patterns via config
4. **Fallback Support** - Handles episodes without AI metadata
5. **Show Name Mapping** - Maps AI variations to consistent folder names

## 📁 Folder Structure

```
data/outputs/
├── ForumDailyNews/
│   ├── 2024/
│   │   ├── ForumDailyNews_ep140_2024-10-27/
│   │   │   ├── clips/
│   │   │   ├── html/
│   │   │   └── meta/
│   │   └── ForumDailyNews_ep141_2024-10-28/
│   └── 2025/
├── BoomAndBust/
│   └── 2024/
│       └── BoomAndBust_ep025_2024-11-15/
├── TheLeDrewShow/
│   └── 2025/
│       └── TheLeDrewShow_ep099_2025-01-10/
└── _uncategorized/
    └── newsroom-recording_20241027_143000/
```

## 🏷️ Episode ID Format

**Standard Format:**
```
{show_folder}_ep{episode_number}_{date}
```

**Examples:**
- `ForumDailyNews_ep140_2024-10-27`
- `BoomAndBust_ep025_2024-11-15`
- `CanadianJustice_epS01E05_2024-12-01`
- `TheLeDrewShow_ep099_2025-01-10`

**Fallback Format** (no AI data):
```
{source_filename}_{timestamp}
```

**Example:**
- `newsroom-recording-oct27_20241027_143000`

## 🎭 Show Name Mapping

The system maps AI-extracted show names to consistent folder names:

| AI-Extracted Name | Folder Name |
|-------------------|-------------|
| "The News Forum" | `thenewsforum` |
| "Forum Daily News" | `ForumDailyNews` |
| "Boom and Bust" | `BoomAndBust` |
| "Boom & Bust" | `BoomAndBust` |
| "Canadian Justice" | `CanadianJustice` |
| "Counterpoint" | `Counterpoint` |
| "Canadian Innovators" | `CanadianInnovators` |
| "The LeDrew Show" | `TheLeDrewShow` |
| "LeDrew Show" | `TheLeDrewShow` |
| "My Generation" | `MyGeneration` |
| "Forum Focus" | `ForumFocus` |
| "Empowered" | `Empowered` |

**Unmapped shows** are automatically slugified (e.g., "Unknown Show" → "unknown-show")

## ⚙️ Configuration

Edit `config/pipeline.yaml`:

```yaml
organization:
  # Folder structure template
  folder_structure: "{show_folder}/{year}"
  
  # Episode ID template
  episode_template: "{show_folder}_ep{episode_number}_{date}"
  
  # Date format
  date_format: "%Y-%m-%d"  # YYYY-MM-DD
  
  # Fallback for episodes without AI data
  fallback_template: "{source_name}_{timestamp}"
  
  # Uncategorized folder name
  uncategorized_folder: "_uncategorized"
```

### Template Variables

**Folder Structure:**
- `{show_folder}` - Mapped show name (e.g., "ForumDailyNews")
- `{year}` - 4-digit year (e.g., "2024")
- `{month}` - 2-digit month (e.g., "10")

**Episode Template:**
- `{show_folder}` - Mapped show name
- `{episode_number}` - Padded episode number (e.g., "140", "025")
- `{date}` - Formatted date (e.g., "2024-10-27")
- `{date_compact}` - Compact date (e.g., "20241027")

**Fallback Template:**
- `{source_name}` - Original filename (slugified)
- `{timestamp}` - Full timestamp (e.g., "20241027_143000")

## 🔧 Customization Examples

### Flat Structure (No Year Folders)

```yaml
organization:
  folder_structure: "{show_folder}"
  episode_template: "{show_folder}_ep{episode_number}_{date}"
```

Result: `data/outputs/ForumDailyNews/ForumDailyNews_ep140_2024-10-27/`

### Year-Month Structure

```yaml
organization:
  folder_structure: "{show_folder}/{year}/{month}"
  episode_template: "{show_folder}_ep{episode_number}_{date}"
```

Result: `data/outputs/ForumDailyNews/2024/10/ForumDailyNews_ep140_2024-10-27/`

### Compact Naming

```yaml
organization:
  folder_structure: "{show_folder}/{year}"
  episode_template: "{show_folder}_{episode_number}_{date_compact}"
  date_format: "%Y%m%d"
```

Result: `data/outputs/ForumDailyNews/2024/ForumDailyNews_140_20241027/`

## 🔍 Usage in Code

```python
from src.core.naming_service import get_naming_service

# Get naming service
naming = get_naming_service()

# Generate episode ID
episode_id = naming.generate_episode_id(
    show_name="Forum Daily News",
    episode_number="140",
    date=datetime(2024, 10, 27)
)
# Returns: "ForumDailyNews_ep140_2024-10-27"

# Get folder path
folder_path = naming.get_episode_folder_path(
    episode_id=episode_id,
    show_name="Forum Daily News",
    date=datetime(2024, 10, 27)
)
# Returns: Path("data/outputs/ForumDailyNews/2024/ForumDailyNews_ep140_2024-10-27")

# Map show name
folder_name = naming.map_show_name("The News Forum")
# Returns: "thenewsforum"

# Parse episode ID
parsed = naming.parse_episode_id("ForumDailyNews_ep140_2024-10-27")
# Returns: {
#     'show_folder': 'ForumDailyNews',
#     'episode_number': '140',
#     'date': datetime(2024, 10, 27)
# }
```

## 📝 Adding New Shows

### Option 1: Via Configuration

Edit `src/core/naming_service.py`:

```python
SHOW_NAME_MAPPING = {
    # Add your show
    "new show name": "NewShowFolder",
    "new show": "NewShowFolder",
}
```

### Option 2: At Runtime

```python
from src.core.naming_service import get_naming_service

naming = get_naming_service()
naming.add_show_mapping("New Show Name", "NewShowFolder")
```

## 🔄 Migration

To reorganize existing episodes with the new naming system:

```powershell
# Coming soon: migration script
python scripts/migrate_episode_naming.py
```

## ✅ Benefits

1. **Organized** - Episodes grouped by show and year
2. **Searchable** - Human-readable episode IDs
3. **Consistent** - Standardized naming across pipeline
4. **Flexible** - Customizable via configuration
5. **Robust** - Fallback for missing metadata
6. **Scalable** - Easy to add new shows

## 🚀 Next Steps

1. ✅ Naming service implemented
2. ✅ Configuration added
3. ⏳ Integrate with pipeline stages
4. ⏳ Create migration script
5. ⏳ Update API endpoints
6. ⏳ Update Streamlit dashboard

## 📚 Related Documentation

- [Pipeline Configuration](../config/pipeline.yaml)
- [API Documentation](API.md)
- [Development Guide](DEVELOPMENT.md)
