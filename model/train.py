import pandas as pd
import numpy as np
import re
import pickle
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

# ─── Step 1: Load data ───────────────────────────────────────────────
print("Loading data...")
df = pd.read_csv(os.path.join(os.path.dirname(__file__), '../data/data.csv'))
print(f"Loaded {len(df)} records")
print(df['label'].value_counts())

# ─── Step 2: Clean text ───────────────────────────────────────────────
def clean_text(text):
    text = str(text).lower()              # lowercase
    text = re.sub(r'[^\w\s]', '', text)  # remove punctuation
    text = re.sub(r'\s+', ' ', text)     # remove extra spaces
    text = text.strip()
    return text

df['clean_text'] = df['text'].apply(clean_text)
print("\nSample cleaned text:")
print(df[['text', 'clean_text', 'label']].head(3))

# ─── Step 3: Feature conversion (TF-IDF) ─────────────────────────────
print("\nConverting text to TF-IDF vectors...")
vectorizer = TfidfVectorizer(max_features=500, ngram_range=(1, 2))
X = vectorizer.fit_transform(df['clean_text'])
y = df['label']

print(f"Feature matrix shape: {X.shape}")

# ─── Step 4: Train/test split ─────────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print(f"Train size: {X_train.shape[0]}, Test size: {X_test.shape[0]}")

# ─── Step 5: Train Logistic Regression ───────────────────────────────
print("\nTraining Logistic Regression model...")
model = LogisticRegression(max_iter=1000, C=1.0, random_state=42)
model.fit(X_train, y_train)

# ─── Step 6: Evaluate ─────────────────────────────────────────────────
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
print(f"\nModel Accuracy: {accuracy:.2%}")
print("\nClassification Report:")
print(classification_report(y_test, y_pred))

# ─── Step 7: Save model and vectorizer ────────────────────────────────
model_dir = os.path.dirname(__file__)
model_path = os.path.join(model_dir, 'model.pkl')
vec_path   = os.path.join(model_dir, 'vectorizer.pkl')

with open(model_path, 'wb') as f:
    pickle.dump(model, f)
with open(vec_path, 'wb') as f:
    pickle.dump(vectorizer, f)

print(f"\nModel saved    -> {model_path}")
print(f"Vectorizer saved -> {vec_path}")

# ─── Step 8: Manual prediction test ──────────────────────────────────
print("\n--- Manual prediction test ---")
test_cases = [
    "severe chest pain cannot breathe sweating",
    "broken arm moderate pain conscious",
    "mild headache no fever",
    "unconscious road accident bleeding head",
]
for case in test_cases:
    cleaned = clean_text(case)
    vec = vectorizer.transform([cleaned])
    pred = model.predict(vec)[0]
    proba = model.predict_proba(vec)[0]
    conf = round(max(proba) * 100, 1)
    print(f"  Input : {case}")
    print(f"  Result: {pred} ({conf}% confidence)\n")

print("Training complete!")
