"""
Configuration file for the English Teaching Telegram Bot
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token_here")
CHANNEL_ID = "@Ingliztiliuzz"

# OpenRouter Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_API_KEY_2 = os.getenv("OPENROUTER_API_KEY_2", "")
OPENROUTER_MODEL = "openai/gpt-oss-120b:free" 
OPENROUTER_MODEL_2 = "tencent/hy3:free"
OPENROUTER_MODEL_3 = "poolside/laguna-xs-2.1:free"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Scheduling Configuration
POST_INTERVAL_HOURS = 4  # Posts every 4 hours
POSTS_PER_DAY = 6  # 6 posts per day (24/4)
TEST_INTERVAL_HOURS = 12  # Tests every 12 hours
TESTS_PER_DAY = 2  # 2 tests per day

# History Configuration
HISTORY_RESET_AFTER = 36  # Reset topic history after 36 posts

# Post Types
POST_TYPE_LESSON = "lesson"
POST_TYPE_TEST = "test"

# File paths
TOPIC_HISTORY_FILE = "topic_history.json"

# Topic and Hashtag Data
TOPICS_DATA = {
    "Grammar & Vocabulary": {
        "topics": [
            "English grammar tips for learners",
            "Common grammar mistakes in English",
            "Daily vocabulary words with meaning",
            "B1 vocabulary list with example sentences",
            "Useful English phrases for daily conversation",
            "Basic English grammar rules PDF",
            "Academic vs informal English vocabulary"
        ],
        "tags": [
            "#GrammarTips", "#GrammarHelp", "#EnglishGrammar101", 
            "#WordOfTheDay", "#VocabularyBuilder", "#EnglishWords", 
            "#ImproveYourGrammar", "#DailyVocabulary"
        ]
    },
    "Phrases & Idioms": {
        "topics": [
            "Most used English idioms with meanings",
            "Phrasal verbs list with examples",
            "English expressions for speaking fluently",
            "Everyday English phrases for beginners",
            "Idioms for English learners PDF",
            "Slang vs idiom difference examples"
        ],
        "tags": [
            "#EnglishIdioms", "#PhrasalVerbs", "#EnglishPhrases", 
            "#SpeakLikeANative", "#IdiomsOfTheDay", "#DailyIdioms", 
            "#EverydayEnglish"
        ]
    },
    "IELTS Focus": {
        "topics": [
            "IELTS writing task 1 and 2 tips",
            "IELTS speaking band 7 sample answers",
            "IELTS reading strategies for high score",
            "IELTS vocabulary for writing and speaking",
            "Common IELTS topics with sample answers",
            "IELTS academic vs general training difference"
        ],
        "tags": [
            "#IELTSTips", "#IELTSPreparation", "#IELTSWriting", 
            "#IELTSSpeaking", "#IELTSReading", "#IELTSVocabulary", 
            "#Band7Plus", "#IELTSPractice"
        ]
    },
    "Writing Skills": {
        "topics": [
            "Connectors for IELTS writing",
            "Formal vs informal writing in English",
            "Common mistakes in English essays"
        ],
        "tags": [
            "#EnglishWriting", "#WritingTips", "#IELTSWriting",
            "#EssayWriting", "#GrammarTips", "#WriteBetter"
        ]
    },
    "Speaking Skills": {
        "topics": [
            "IELTS speaking part 1 sample questions",
            "Useful phrases for speaking fluently",
            "How to extend answers in speaking test"
        ],
        "tags": [
            "#EnglishSpeaking", "#SpeakEnglish", "#FluentEnglish",
            "#SpeakLikeANative", "#IELTSSpeaking", "#SpeakingTips"
        ]
    }
}

GENERAL_TAGS = [
    "#LearnEnglish", "#EnglishTips", "#EnglishGrammar", 
    "#EnglishVocabulary", "#EnglishLearning", "#SpeakEnglish", 
    "#EnglishForEveryone", "#EnglishMadeEasy", "#FluentEnglish", 
    "#StudyEnglish"
]
