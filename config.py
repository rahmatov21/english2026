"""
Configuration file for the English Teaching Telegram Bot
Expanded with 10 structured categories, 120+ targeted topics, and complex memory settings.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token_here")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@ingliztiliuzz")

# OpenRouter Configuration (Updated with tested high-performance active models)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_API_KEY_2 = os.getenv("OPENROUTER_API_KEY_2", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "cohere/north-mini-code:free")
OPENROUTER_MODEL_2 = os.getenv("OPENROUTER_MODEL_2", "nvidia/nemotron-3-ultra-550b-a55b:free")
OPENROUTER_MODEL_3 = os.getenv("OPENROUTER_MODEL_3", "nvidia/nemotron-3.5-lightning:free")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Scheduling Configuration
POST_INTERVAL_HOURS = int(os.getenv("POST_INTERVAL_HOURS", 4))    # Posts every 4 hours (6 posts/day)
POSTS_PER_DAY = 6
TEST_INTERVAL_HOURS = int(os.getenv("TEST_INTERVAL_HOURS", 12))   # Tests every 12 hours (2 tests/day)
TESTS_PER_DAY = 2

# Advanced Memory Configuration
RECENT_TOPICS_COOLDOWN = 60          # Do not repeat a topic until at least 60 other topics have been posted
MEMORY_BLACKLIST_LIMIT = 100         # Number of recently taught words/idioms passed in the AI prompt forbidden list
MEMORY_HISTORY_SUMMARY_LIMIT = 25    # Detailed lesson records provided to the AI prompt context
HISTORY_RESET_AFTER = 120            # Topic cycle reset threshold

# Post Types
POST_TYPE_LESSON = "lesson"
POST_TYPE_TEST = "test"

# File paths
TOPIC_HISTORY_FILE = "topic_history.json"

# Curriculum Categories Rotation Sequence
# Ensures consecutive posts cover different skills throughout the day
CATEGORY_ROTATION = [
    "High-Impact Vocabulary",
    "Phrasal Verbs in Action",
    "Common Mistakes & Confusing Pairs",
    "Real-World Idioms & Colloquialisms",
    "Practical Grammar Mastery",
    "Conversational Fluency & Native Swaps",
    "Collocations & Natural Word Combos",
    "Professional & Business English",
    "Pronunciation & Spoken English Secrets",
    "Everyday Life & Travel English",
]

# Comprehensive 120+ Topic Curriculum across 10 Rich Categories
TOPICS_DATA = {
    "High-Impact Vocabulary": {
        "topics": [
            "Powerful verbs to replace common everyday actions (walk, eat, see)",
            "Precision adjectives that replace 'Very' (very tired, very angry, very cold)",
            "Sophisticated words for describing feelings and emotional states",
            "Atmosphere, weather, and sensory descriptive vocabulary (C1 level)",
            "Nuanced personality traits: describing positive human character",
            "Nuanced personality traits: describing negative or difficult behaviors",
            "High-level connectors and transition words for articulate speaking",
            "B2-C1 words for expressing certainty, doubt, and possibility",
            "Elevated academic and intellectual vocabulary for discussions",
            "Describing time, speed, and changes with vibrant vocabulary",
            "Describing beauty, aesthetics, and appearance with elegance",
            "Words for size, scale, and importance (massive vs minute)",
        ],
        "tags": ["#VocabularyBuilder", "#AdvancedVocabulary", "#C1English", "#WordOfTheDay", "#LearnWords"]
    },
    "Phrasal Verbs in Action": {
        "topics": [
            "Essential phrasal verbs for office life, productivity, and tasks",
            "Phrasal verbs for social life, meeting friends, and hanging out",
            "Phrasal verbs for travel, transportation, and airport journeys",
            "Phrasal verbs for overcoming challenges and dealing with setbacks",
            "Phrasal verbs for relationships, dating, and family dynamics",
            "Phrasal verbs with 'LOOK' (look up, look down on, look forward to)",
            "Phrasal verbs with 'BRING' (bring up, bring about, bring down)",
            "Phrasal verbs with 'TAKE' (take aback, take after, take over)",
            "Phrasal verbs with 'COME' (come across, come up with, come down with)",
            "Phrasal verbs with 'PUT' (put off, put up with, put across)",
            "Phrasal verbs for technology, phones, and digital communication",
            "Phrasal verbs for managing money, budgeting, and shopping",
        ],
        "tags": ["#PhrasalVerbs", "#DailyEnglish", "#NaturalEnglish", "#SpeakLikeANative", "#VerbsInAction"]
    },
    "Common Mistakes & Confusing Pairs": {
        "topics": [
            "Say vs Tell vs Speak vs Talk: the exact rules natives follow",
            "Lend vs Borrow vs Rent: never mix them up again",
            "Like vs As vs As if: mastering comparisons and roles",
            "Remember to do vs Remember doing: gerund vs infinitive meaning shifts",
            "Fewer vs Less: countables vs uncountables in real life",
            "Lie vs Lay vs Laid: tenses and transitive rules made simple",
            "Sensible vs Sensitive: false friends and confusing adjectives",
            "Since vs For vs During: expressing duration and time points accurately",
            "Advise vs Advice, Affect vs Effect: spelling and usage traps",
            "Economic vs Economical, Classic vs Classical: subtle differences",
            "Look forward to + Verb-ing: avoiding the most common email mistake",
            "Beside vs Besides, Especially vs Specially: precise usage",
        ],
        "tags": ["#CommonMistakes", "#GrammarMistakes", "#EnglishTips", "#ConfusedWords", "#CorrectYourEnglish"]
    },
    "Real-World Idioms & Colloquialisms": {
        "topics": [
            "Idioms for time pressure, deadlines, and running late",
            "Idioms for hard times, perseverance, and mental resilience",
            "Idioms for success, triumph, and reaching major goals",
            "Idioms for decision-making, dilemmas, and second thoughts",
            "Idioms about communication, sharing secrets, and honesty",
            "Idioms connected to money, cost, and wealth (beyond 'cost an arm and leg')",
            "Food and cooking idioms used in everyday conversations",
            "Body part idioms (eyes, ears, feet, hands) for vivid expressions",
            "Weather and nature idioms used in work and casual talks",
            "Idioms for conflict, arguments, and clearing the air",
            "Animal metaphors and idioms for human behavior",
            "British vs American idiom equivalents in modern culture",
        ],
        "tags": ["#EnglishIdioms", "#IdiomOfTheDay", "#SlangAndIdioms", "#SpeakEnglish", "#FluentExpressions"]
    },
    "Practical Grammar Mastery": {
        "topics": [
            "Present Perfect vs Past Simple: when natives actually choose which",
            "Used to vs Be Used to vs Get Used to: the 3 distinct structures",
            "Conditionals for real life: 2nd vs 3rd conditional for regrets & wishes",
            "Modals of deduction: Must have been, Can't have been, Might be",
            "Wish & If Only: expressing past regrets vs present desires",
            "Passive voice in real contexts: when and why to sound objective",
            "Inversion for emphasis (Never have I..., Seldom do we...)",
            "Relative clauses (who, which, that, whose): speaking smoothly without clutter",
            "Direct vs Indirect speech: natural reporting in conversation",
            "Mixed conditionals: connecting past events to present results",
            "Subjunctive mood in modern English (I insist that he be...)",
            "Quantifiers: Each, Every, Both, Either, Neither mastered",
        ],
        "tags": ["#GrammarMastery", "#EnglishGrammar", "#GrammarRules", "#GrammarInUse", "#MasterEnglish"]
    },
    "Conversational Fluency & Native Swaps": {
        "topics": [
            "Natural alternatives to 'I think' (In my view, It seems to me, From my perspective)",
            "Polite ways to say 'No' and reject invitations diplomatically",
            "Better ways to say 'I'm busy' (swamped, tied up, snowed under)",
            "Expressing agreement with style (beyond just 'I agree with you')",
            "Diplomatic disagreement: challenging opinions without being rude",
            "Native conversation starters for casual and social encounters",
            "Natural filler words and pauses that make you sound like a native",
            "Softening harsh statements using modal hedging (could, might, possibly)",
            "Reacting with genuine emotion (surprise, sympathy, delight, shock)",
            "Ending a conversation smoothly and making a polite exit",
            "Asking for clarification or repetition naturally without saying 'What?'",
            "Giving authentic compliments on achievements, appearance, and work",
        ],
        "tags": ["#FluentEnglish", "#SpeakingHacks", "#NativeSwaps", "#DailyConversation", "#ConversationalEnglish"]
    },
    "Collocations & Natural Word Combos": {
        "topics": [
            "High-frequency collocations with MAKE (make an effort, make amends)",
            "High-frequency collocations with DO (do business, do justice, do harm)",
            "High-frequency collocations with TAKE (take for granted, take a chance)",
            "High-frequency collocations with HAVE & GET in daily speech",
            "Strong adverb + adjective combinations (bitterly disappointed, highly likely)",
            "Verb + noun collocations for expressing emotions and opinions",
            "Essential dependent prepositions after verbs (rely on, insist on, stem from)",
            "Essential dependent prepositions after adjectives (prone to, capable of)",
            "Collocations for discussing problems and delivering solutions",
            "Collocations for describing weather, feelings, and sensations",
            "Collocations for success, failure, and risk-taking",
            "Business and contract collocations (reach an agreement, meet demands)",
        ],
        "tags": ["#Collocations", "#NaturalPhrasing", "#WordPartnerships", "#LearnEnglishFast", "#EnglishVocabulary"]
    },
    "Professional & Business English": {
        "topics": [
            "Polite and professional email opening and closing lines",
            "Following up on emails and proposals without sounding pushy",
            "Participating effectively in meetings: pitching ideas and agreeing",
            "Disagreeing constructively in business meetings",
            "Delivering constructive feedback and soft criticisms to colleagues",
            "Negotiation English: bargaining, making concessions, and closing deals",
            "Explaining delays, technical issues, and unforeseen setbacks",
            "Professional small talk with international clients and coworkers",
            "Describing company growth, market trends, and data insights",
            "Executive summaries: presenting solutions concisely to leadership",
            "Job interview power answers: describing strengths and accomplishments",
            "Professional telephone and video conference etiquette phrases",
        ],
        "tags": ["#BusinessEnglish", "#CareerEnglish", "#EmailEtiquette", "#WorkplaceEnglish", "#ProfessionalDevelopment"]
    },
    "Pronunciation & Spoken English Secrets": {
        "topics": [
            "Connected speech: how natives blend words (linking consonant to vowel)",
            "The Flap 'T' and Glottal Stop in modern American and British speech",
            "Silent letters that learners trip on (doubt, muscle, receipt, island)",
            "Word stress shifts: noun vs verb pronunciation (reCORD vs REcord)",
            "Weak forms of auxiliary verbs and prepositions (to, for, have, been)",
            "Intonation patterns: sounding enthusiastic, polite, vs sarcastic",
            "Contracted forms in fast speech (gonna, wanna, shoulda, coulda)",
            "Homophones that cause confusion (their/there/they're, bare/bear)",
            "Sentence rhythm: content words vs function words in English",
            "Pronouncing '-ed' endings correctly: /t/, /d/, and /ɪd/ rules",
            "The Schwa sound /ə/: the most important sound in the English language",
            "Tricky vowel distinctions: ship vs sheep, pull vs pool, bad vs bed",
        ],
        "tags": ["#PronunciationTips", "#SpeakFluent", "#SpokenEnglish", "#EnglishSounds", "#AccentReduction"]
    },
    "Everyday Life & Travel English": {
        "topics": [
            "Ordering with confidence at coffee shops, diners, and restaurants",
            "Navigating international airports: check-in, customs, and boarding",
            "Hotel situations: requesting room upgrades, reporting issues, and checkout",
            "Public transit, taking taxis/rideshares, and asking for directions",
            "Handling emergencies, medical visits, and describing symptoms to a doctor",
            "Shopping, returns, asking for discounts, and trying on clothes",
            "Making reservations, cancellations, and rescheduling appointments",
            "Inviting neighbors or acquaintances and hosting guests at home",
            "Car rental, road trips, and dealing with vehicle issues abroad",
            "Banking, currency exchange, and using ATMs safely overseas",
            "Attending social events, weddings, and celebrations politely",
            "Handling misunderstandings, apologizing sincerely, and restoring goodwill",
        ],
        "tags": ["#TravelEnglish", "#EverydayEnglish", "#RealWorldEnglish", "#LifeInEnglish", "#DailyEnglishPractice"]
    }
}

GENERAL_TAGS = [
    "#LearnEnglish", "#ImproveYourEnglish", "#EnglishChannel",
    "#FluentEnglish", "#EnglishStudy", "#EnglishTips"
]
