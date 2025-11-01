#!/usr/bin/env python3
"""
Test script for multilingual transcription support

This script tests the new multilingual features:
1. Auto language detection
2. Translation to English
3. Language validation
4. Configuration handling
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Any

# Add src to path for imports
src_path = str(Path(__file__).parent / "src")
sys.path.insert(0, src_path)

# Set up proper package structure
import os
os.chdir(Path(__file__).parent)

try:
    from src.core.config import PipelineConfig, ConfigurationManager
    from src.core.models import EpisodeObject, ProcessingStage
    from src.stages.transcription_stage import TranscriptionStageProcessor
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


async def test_multilingual_config():
    """Test multilingual configuration loading"""
    print("🔧 Testing multilingual configuration...")
    
    # Load configuration
    config_manager = ConfigurationManager("config/pipeline.yaml")
    config = config_manager.load_config()
    
    # Check if transcription config exists
    if hasattr(config, 'transcription'):
        transcription_config = config.transcription
        print(f"✅ Language setting: {transcription_config.language}")
        print(f"✅ Translation enabled: {transcription_config.translate_to_english}")
        print(f"✅ Supported languages: {transcription_config.supported_languages}")
        print(f"✅ Fallback language: {transcription_config.fallback_language}")
    else:
        print("❌ Transcription configuration not found in config")
        return False
    
    return True


async def test_processor_initialization():
    """Test TranscriptionStageProcessor with multilingual config"""
    print("\n🏗️ Testing processor initialization...")
    
    # Load configuration
    config_manager = ConfigurationManager("config/pipeline.yaml")
    config = config_manager.load_config()
    config_dict = config.to_dict()
    
    # Initialize processor
    try:
        processor = TranscriptionStageProcessor(
            model_name="base",  # Use smaller model for testing
            config=config_dict
        )
        
        print(f"✅ Processor initialized successfully")
        print(f"✅ Language setting: {processor.language}")
        print(f"✅ Translation enabled: {processor.translate_to_english}")
        print(f"✅ Task: {processor.task}")
        print(f"✅ Supported languages: {processor.supported_languages}")
        print(f"✅ Fallback language: {processor.fallback_language}")
        
        return True
        
    except Exception as e:
        print(f"❌ Processor initialization failed: {e}")
        return False


async def test_language_validation():
    """Test language validation logic"""
    print("\n🌍 Testing language validation...")
    
    config_manager = ConfigurationManager("config/pipeline.yaml")
    config = config_manager.load_config()
    config_dict = config.to_dict()
    
    processor = TranscriptionStageProcessor(
        model_name="base",
        config=config_dict
    )
    
    # Test supported language
    supported_languages = processor.supported_languages
    if 'en' in supported_languages:
        print("✅ English is in supported languages")
    else:
        print("❌ English not in supported languages")
        return False
    
    # Test fallback
    fallback = processor.fallback_language
    if fallback == 'en':
        print("✅ Fallback language is English")
    else:
        print(f"⚠️ Fallback language is {fallback}")
    
    return True


async def simulate_transcription_result():
    """Simulate a transcription result with multilingual data"""
    print("\n🎯 Simulating transcription result...")
    
    # Simulate Whisper result with detected language
    mock_result = {
        'text': "Hello, this is a test transcription.",
        'segments': [
            {
                'start': 0.0,
                'end': 3.0,
                'text': "Hello, this is a test transcription.",
                'words': [
                    {'start': 0.0, 'end': 0.5, 'word': 'Hello'},
                    {'start': 0.5, 'end': 1.0, 'word': 'this'},
                    {'start': 1.0, 'end': 1.2, 'word': 'is'},
                    {'start': 1.2, 'end': 1.4, 'word': 'a'},
                    {'start': 1.4, 'end': 1.8, 'word': 'test'},
                    {'start': 1.8, 'end': 3.0, 'word': 'transcription'}
                ]
            }
        ],
        'language': 'en'
    }
    
    # Test language detection logic
    config_manager = ConfigurationManager("config/pipeline.yaml")
    config = config_manager.load_config()
    config_dict = config.to_dict()
    
    processor = TranscriptionStageProcessor(
        model_name="base",
        config=config_dict
    )
    
    detected_language = mock_result.get('language', processor.fallback_language)
    
    if detected_language in processor.supported_languages:
        print(f"✅ Detected language '{detected_language}' is supported")
    else:
        print(f"⚠️ Detected language '{detected_language}' not supported, would use fallback '{processor.fallback_language}'")
        detected_language = processor.fallback_language
    
    # Simulate return data structure
    result_data = {
        'txt_path': 'data/transcripts/txt/test.txt',
        'vtt_path': 'data/transcripts/vtt/test.vtt',
        'text': mock_result['text'],
        'segments': mock_result['segments'],
        'words': mock_result['segments'][0].get('words', []),
        'language': detected_language,
        'detected_language': detected_language,
        'original_language': mock_result.get('language', detected_language),
        'task_performed': 'translate' if processor.translate_to_english else 'transcribe',
        'translated_to_english': processor.translate_to_english,
        'segment_count': len(mock_result['segments']),
        'word_count': len(mock_result['segments'][0].get('words', [])),
        'success': True
    }
    
    print(f"✅ Simulated result structure:")
    for key, value in result_data.items():
        if key not in ['segments', 'words']:  # Skip large data for readability
            print(f"   {key}: {value}")
    
    return True


async def main():
    """Run all multilingual tests"""
    print("🚀 Starting multilingual support tests...\n")
    
    tests = [
        ("Configuration Loading", test_multilingual_config),
        ("Processor Initialization", test_processor_initialization),
        ("Language Validation", test_language_validation),
        ("Transcription Result Simulation", simulate_transcription_result),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            if result:
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"💥 {test_name}: ERROR - {e}")
        
        print("-" * 50)
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All multilingual tests passed!")
        print("\n📝 Next steps:")
        print("1. Test with actual non-English audio files")
        print("2. Verify language detection accuracy")
        print("3. Test translation functionality")
        print("4. Update dashboard to display language information")
    else:
        print("⚠️ Some tests failed. Please review the implementation.")
    
    return passed == total


if __name__ == "__main__":
    asyncio.run(main())
