"""
Configuration file for the English Teaching Telegram Bot
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token_here")
CHANNEL_ID = "@ingliztiliuzz"

# OpenRouter Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_API_KEY_2 = os.getenv("OPENROUTER_API_KEY_2", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "minimax/minimax-m3.1-flash:free")
OPENROUTER_MODEL_2 = os.getenv("OPENROUTER_MODEL_2", "cohere/north-mini-code:free")
OPENROUTER_MODEL_3 = os.getenv("OPENROUTER_MODEL_3", "poolside/laguna-xs-2.1:free")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Scheduling Configuration
POST_INTERVAL_HOURS = int(os.getenv("POST_INTERVAL_HOURS", 4))  # Posts every 4 hours
POSTS_PER_DAY = 6  # 6 posts per day (24/4)
TEST_INTERVAL_HOURS = int(os.getenv("TEST_INTERVAL_HOURS", 12))  # Tests every 12 hours
TESTS_PER_DAY = 2  # 2 tests per day (24/12)

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
            "Basic English grammar rules",
            "Academic vs informal English vocabulary",
            "Must-know vocabulary",
            "Confused words"
        ],
        "tags": [
            "#GrammarTips", "#GrammarHelp", "#EnglishGrammar101", 
            "#WordOfTheDay", "#VocabularyBuilder", "#EnglishWords", 
            "#ImproveYourGrammar", "#DailyVocabulary"
        ]
    },
    "Phrases & Idioms": {
        "topics": [
            "Useful English phrases for daily conversation",
            "Most used English idioms with meanings",
            "Phrasal verbs list with examples",
            "English expressions for speaking fluently",
            "Everyday English phrases for beginners",
            "Idioms for English learners"
        ],
        "tags": [
            "#EnglishIdioms", "#PhrasalVerbs", "#EnglishPhrases", 
            "#SpeakLikeANative", "#IdiomsOfTheDay", "#DailyIdioms", 
            "#EverydayEnglish"
        ]
    }
}

GENERAL_TAGS = [
    "#LearnEnglish", "#EnglishTips", "#EnglishGrammar", 
    "#EnglishVocabulary", "#EnglishLearning", "#SpeakEnglish", 
    "#EnglishForEveryone", "#EnglishMadeEasy", "#FluentEnglish", 
    "#StudyEnglish"
]
