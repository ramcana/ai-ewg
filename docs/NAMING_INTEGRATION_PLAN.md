# Naming Service Integration Plan

## 🎯 Overview

This document outlines the integration of the naming service across all pipeline stages and modules.

## 📋 Integration Points

### 1. Discovery Stage ✅ DONE
**File:** `src/core/normalizer.py`

**Changes:**
- Import naming service
- Use fallback naming at discovery (no AI data yet)
- Generate temporary episode ID from filename

**Result:**
```
newsroom-recording-oct27_20241027_143000
```

### 2. Enrichment Stage ⏳ IN PROGRESS
**File:** `src/core/pipeline.py` - `_process_enrichment_stage()`

**Changes:**
- After AI extraction, regenerate episode ID with show name and episode number
- Update episode object with new ID
- Update all file paths to use new structure
- Update database with new ID

**Result:**
```
ForumDailyNews_ep140_2024-10-27
```

**Code Location:**
```python
# After enrichment completes (line ~550)
if enrichment_result.show_name and enrichment_result.episode_number:
    naming_service = get_naming_service()
    new_episode_id = naming_service.generate_episode_id(
        show_name=enrichment_result.show_name,
        episode_number=enrichment_result.episode_number,
        date=episode.created_at or datetime.now()
    )
    
    # Rename episode and update paths
    old_id = episode.episode_id
    episode.episode_id = new_episode_id
    
    # Update registry
    registry.rename_episode(old_id, new_episode_id)
```

### 3. Clip Generation ⏳ PENDING
**Files:**
- `src/core/clip_discovery.py`
- `src/core/clip_export.py`
- `src/api/clip_endpoints.py`

**Changes:**
- Use naming service to get episode folder path
- Update clip output paths: `data/outputs/{show_folder}/{year}/{episode_id}/clips/`
- Update clip IDs to include show folder

**Current:**
```
data/outputs/newsroom-2024-bb580/clips/clip_1/
```

**New:**
```
data/outputs/ForumDailyNews/2024/ForumDailyNews_ep140_2024-10-27/clips/clip_1/
```

**Code Changes:**
```python
# In clip_endpoints.py
naming_service = get_naming_service()
episode_folder = naming_service.get_episode_folder_path(
    episode_id=episode.episode_id,
    show_name=episode.enrichment.show_name if episode.enrichment else None,
    date=episode.created_at
)

output_path = episode_folder / "clips" / clip.id / f"{aspect_ratio}_{variant}.mp4"
```

### 4. Social Media Packages ⏳ PENDING
**Files:**
- `src/core/package_generator.py`
- `src/api/social_endpoints.py`

**Changes:**
- Use naming service for package paths
- Update package structure: `data/social_packages/{show_folder}/{year}/{episode_id}/{platform}/`

**Current:**
```
data/social_packages/newsroom-2024-bb580/youtube/
```

**New:**
```
data/social_packages/ForumDailyNews/2024/ForumDailyNews_ep140_2024-10-27/youtube/
```

**Code Changes:**
```python
# In package_generator.py
naming_service = get_naming_service()
episode_folder = naming_service.get_episode_folder_path(
    episode_id=episode_id,
    show_name=show_name,
    date=date,
    base_path="data/social_packages"
)

package_path = episode_folder / platform
```

### 5. Rendering Stage ⏳ PENDING
**File:** `src/stages/rendering_stage.py`

**Changes:**
- Use naming service for HTML output paths
- Update asset paths to match new structure

**Current:**
```
data/outputs/newsroom-2024-bb580/html/
```

**New:**
```
data/outputs/ForumDailyNews/2024/ForumDailyNews_ep140_2024-10-27/html/
```

### 6. API Endpoints ⏳ PENDING
**Files:**
- `src/api/endpoints.py`
- `src/api/clip_endpoints.py`
- `src/api/social_endpoints.py`

**Changes:**
- Return new episode IDs in responses
- Update path resolution for file serving
- Add show folder filtering

**New Endpoints:**
```
GET /shows - List all shows
GET /shows/{show_folder}/episodes - List episodes for show
GET /episodes/{episode_id} - Get episode (supports both old and new IDs)
```

### 7. Streamlit Dashboard ⏳ PENDING
**Files:**
- `dashboard.py`
- `components/clips.py`
- `components/social_generator.py`

**Changes:**
- Group episodes by show
- Display show folders in sidebar
- Update file path resolution

**UI Changes:**
```
📁 Shows
  ├── ForumDailyNews (15 episodes)
  ├── BoomAndBust (8 episodes)
  └── TheLeDrewShow (12 episodes)
```

### 8. Database Schema ⏳ PENDING
**File:** `src/core/database.py`

**Changes:**
- Add `show_folder` column to episodes table
- Add index on `show_folder` for filtering
- Migration script for existing data

**SQL:**
```sql
ALTER TABLE episodes ADD COLUMN show_folder TEXT;
CREATE INDEX idx_episodes_show_folder ON episodes(show_folder);
```

## 🔄 Migration Strategy

### Phase 1: Soft Migration (Backward Compatible)
1. ✅ Implement naming service
2. ✅ Update discovery to use fallback naming
3. ⏳ Update enrichment to regenerate IDs
4. ⏳ Support both old and new episode IDs in API
5. ⏳ Update all output paths to use new structure

### Phase 2: Hard Migration (Breaking Changes)
1. Create migration script to rename existing episodes
2. Update database with new IDs
3. Reorganize file system
4. Remove old ID support

### Migration Script Structure:
```python
# scripts/migrate_episode_naming.py

1. Load all episodes from database
2. For each episode:
   a. Extract show name from enrichment
   b. Generate new episode ID
   c. Create new folder structure
   d. Move all files (clips, html, packages)
   e. Update database
   f. Update clip registry
3. Clean up old folders
4. Verify migration
```

## 📊 Testing Plan

### Unit Tests
- ✅ Naming service generation
- ✅ Show name mapping
- ⏳ Episode ID regeneration
- ⏳ Path resolution

### Integration Tests
- ⏳ Full pipeline with new naming
- ⏳ Clip generation with new paths
- ⏳ Social package generation
- ⏳ API endpoint responses

### Manual Tests
- ⏳ Process new episode end-to-end
- ⏳ Migrate existing episode
- ⏳ Verify all files in correct locations
- ⏳ Test Streamlit dashboard

## 🚀 Rollout Plan

### Week 1: Core Integration
- ✅ Day 1: Naming service implementation
- ✅ Day 2: Discovery stage integration
- ⏳ Day 3: Enrichment stage integration
- ⏳ Day 4: Testing and bug fixes

### Week 2: Module Integration
- ⏳ Day 1: Clip generation integration
- ⏳ Day 2: Social media integration
- ⏳ Day 3: API updates
- ⏳ Day 4: Dashboard updates

### Week 3: Migration
- ⏳ Day 1: Migration script development
- ⏳ Day 2: Test migration on sample data
- ⏳ Day 3: Full migration
- ⏳ Day 4: Verification and cleanup

## 📝 Configuration Changes

Users can customize naming via `config/pipeline.yaml`:

```yaml
organization:
  # Folder structure
  folder_structure: "{show_folder}/{year}"
  
  # Episode naming
  episode_template: "{show_folder}_ep{episode_number}_{date}"
  
  # Date format
  date_format: "%Y-%m-%d"
```

## ✅ Success Criteria

1. All new episodes use structured naming
2. Episodes organized by show and year
3. Clip and social packages in correct locations
4. API returns correct paths
5. Dashboard displays organized view
6. Migration script works without data loss
7. Backward compatibility maintained during transition

## 🔗 Related Documentation

- [Naming System Guide](NAMING_SYSTEM.md)
- [Pipeline Configuration](../config/pipeline.yaml)
- [API Documentation](API.md)
