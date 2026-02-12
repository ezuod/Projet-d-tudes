import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# Modèle RoBERTa fine-tuné pour sentiment analysis
model_name = "cardiffnlp/twitter-roberta-base-sentiment"

# Charger tokenizer + modèle
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name)

# Vérifier si GPU disponible
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

print("Device utilisé :", device)

text = "love"

# Tokenisation
inputs = tokenizer(text, return_tensors="pt").to(device)

# Inference
with torch.no_grad():
    outputs = model(**inputs)

# Probabilités
logits = outputs.logits
probs = torch.nn.functional.softmax(logits, dim=-1)

print("Probabilités :", probs)

labels = ["Negative", "Neutral", "Positive"]

predicted_class = torch.argmax(probs).item()
print("Classe prédite :", labels[predicted_class])