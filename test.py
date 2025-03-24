import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
nltk.download('averaged_perceptron_tagger_eng')
import re

def clean_text(text):
    """
    Clean and normalize the input text.
    
    Steps:
      1. Lowercase the text.
      2. Remove HTML tags (if any).
      3. Remove unwanted punctuation, preserving hyphens and colons.
      4. Remove extra whitespace.
    
    Args:
        text (str): Raw input text.
    
    Returns:
        str: Cleaned text.
    """
    # Convert text to lowercase
    text = text.lower()
    
    # Remove HTML tags, if present
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove punctuation except hyphens and colons (needed for dates/times)
    text = re.sub(r'[^a-z0-9\s\-:]', '', text)
    
    # Replace multiple spaces with a single space and strip leading/trailing spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def tokenize_text(text):
    """
    Tokenize the cleaned text into sentences and then into words.
    
    Args:
        text (str): Cleaned text.
    
    Returns:
        list: A list of sentences, where each sentence is a list of word tokens.
    """
    # Split text into sentences
    sentences = sent_tokenize(text)
    # For each sentence, split it into word tokens
    tokens = [word_tokenize(sentence) for sentence in sentences]
    return tokens

import nltk

def pos_tag_tokens(tokenized_sentences):
    """
    Tag each token in every sentence with its part of speech.
    
    Args:
        tokenized_sentences (list): A list of lists, where each inner list contains word tokens from a sentence.
    
    Returns:
        list: A list of lists, where each inner list contains tuples (word, POS tag).
    """
    # Tag each sentence's tokens using NLTK's pos_tag
    tagged_sentences = [nltk.pos_tag(sentence) for sentence in tokenized_sentences]
    return tagged_sentences

def extract_course_codes(self, text):
    """
    Extract course codes from the input text using the defined regex pattern.
    
    Args:
        text (str): Raw input text.
    
    Returns:
        list: A list of course codes found in the text.
    """
    # Use the pre-compiled regex pattern to find all occurrences of course codes
    course_codes = self.course_code_pattern.findall(text)
    # Optionally, remove duplicates by converting to a set and back to a list
    return list(set(course_codes))
    
# Example usage within __main__:
if __name__ == '__main__':
    sample_text = "I need to review MATH201 and PHYS101. MATH201 is my primary course."
    
    print("Extracted course codes:", extract_course_codes(sample_text))
