# =========================================
# IMPORT REQUIRED LIBRARIES
# =========================================

import json
import os
import pickle

# Converts text into numerical vectors (important for ML)
from sklearn.feature_extraction.text import TfidfVectorizer

# Classification algorithm (simple + effective)
from sklearn.linear_model import LogisticRegression


# =========================================
# LOAD INTENT DATASET (intents.json)
# =========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# This file contains all patterns (inputs) and tags (labels)
with open(os.path.join(BASE_DIR, "intents.json")) as file:
    data = json.load(file)

patterns = []   # user sentences
labels = []     # corresponding intent tags


# =========================================
# PREPARE TRAINING DATA
# =========================================

# Loop through each intent
for intent in data["intents"]:
    
    tag = intent["tag"]   # label (e.g., greeting)

    # Loop through all example sentences
    for pattern in intent["patterns"]:
        patterns.append(pattern)
        labels.append(tag)


# =========================================
# TEXT → NUMERIC CONVERSION (TF-IDF)
# =========================================

"""
Machine learning models cannot understand text.
So we convert text into numbers using TF-IDF.

- lowercase=True: Converts all characters to lowercase before tokenizing.
- stop_words='english': Removes common English words (e.g., 'the', 'is', 'in').
"""

# Enhanced vectorizer with preprocessing and short phrase coverage.
vectorizer = TfidfVectorizer(
    lowercase=True,
    stop_words=None, # Removed english stop words for multilingual support
    ngram_range=(1, 2),
    min_df=1,        # Set to 1 to ensure all patterns are captured
    sublinear_tf=True,
)

# Learn vocabulary + transform text
X = vectorizer.fit_transform(patterns)


# =========================================
# TRAIN CLASSIFICATION MODEL
# =========================================

"""
We use Logistic Regression:
- Fast
- Works well for text classification
"""

model = LogisticRegression(max_iter=1000, class_weight="balanced")

# Train model
model.fit(X, labels)


# =========================================
# SAVE MODEL + VECTORIZER
# =========================================

"""
We save both:
1. model → for predictions
2. vectorizer → to convert future input into numbers
"""

pickle.dump(model, open(os.path.join(BASE_DIR, "intent_model.pkl"), "wb"))
pickle.dump(vectorizer, open(os.path.join(BASE_DIR, "vectorizer.pkl"), "wb"))


# =========================================
# SUCCESS MESSAGE
# =========================================

print("Model trained and saved successfully with improved preprocessing!")
