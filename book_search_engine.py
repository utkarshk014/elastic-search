import os
import time
import requests
import re
from elasticsearch import Elasticsearch
from bs4 import BeautifulSoup
import json

elastic_host = os.getenv('ELASTIC_HOST', 'http://localhost:9200')
print(f"Looking for Elasticsearch at: {elastic_host}")

es = Elasticsearch([elastic_host])

max_retries = 30
retry_count = 0

while retry_count < max_retries:
    try:
        info = es.info()
        print("✅ Great! Elasticsearch is responding!")
        print(f"   Version: {info['version']['number']}")
        print(f"   Cluster: {info['cluster_name']}")
        break
    except Exception as e:
        retry_count += 1
        if retry_count < max_retries:
            print(f"   Attempt {retry_count}: Still waiting... ({e})")
            time.sleep(2)
        else:
            print(f"❌ Oops! Can't connect to Elasticsearch after {max_retries} attempts: {e}")
            print("   Make sure Docker is running and Elasticsearch is up!")
            exit(1)


INDEX_NAME = "gutenberg_books"

# delete index if it exists
if es.indices.exists(index=INDEX_NAME):
    print(f"Found existing index '{INDEX_NAME}' - let's delete it for a fresh start!")
    es.indices.delete(index=INDEX_NAME)
    print("   Deleted old index")


mapping = {
    "mappings": {
        "properties": {
            "title": {
                "type": "text",
                "analyzer": "standard"
            },
            "author": {
                "type": "text",
                "analyzer": "standard"
            },
            "content": {
                "type": "text",
                "analyzer": "standard"
            },
            "genre": {
                "type": "keyword"
            },
            "book_id": {
                "type": "keyword"
            },
            "chapter": {
                "type": "text"
            },
            "publication_year": {
                "type": "integer"
            },
            "word_count": {
                "type": "integer"
            }
        }
    }
}

es.indices.create(index=INDEX_NAME, body=mapping)


books_to_download = [
    {"id": 2701, "title": "Moby Dick", "author": "Herman Melville", "genre": "Adventure"},
    {"id": 11, "title": "Alice's Adventures in Wonderland", "author": "Lewis Carroll", "genre": "Fantasy"},
    {"id": 76, "title": "Adventures of Huckleberry Finn", "author": "Mark Twain", "genre": "Adventure"},
    {"id": 74, "title": "The Adventures of Tom Sawyer", "author": "Mark Twain", "genre": "Adventure"},
    {"id": 345, "title": "Dracula", "author": "Bram Stoker", "genre": "Horror"},
    {"id": 174, "title": "The Picture of Dorian Gray", "author": "Oscar Wilde", "genre": "Gothic"},
    {"id": 514, "title": "Little Women", "author": "Louisa May Alcott", "genre": "Fiction"},
    {"id": 46, "title": "A Christmas Carol", "author": "Charles Dickens", "genre": "Fiction"},
    {"id": 1342, "title": "Pride and Prejudice", "author": "Jane Austen", "genre": "Romance"},
    {"id": 84, "title": "Frankenstein", "author": "Mary Shelley", "genre": "Gothic"}
]

def download_gutenberg_book(book_id, title, author, genre):
    try:
        url = f"https://www.gutenberg.org/files/{book_id}/{book_id}-0.txt"
        print(f"   Downloading {title} by {author}...")
        
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            text = response.text
            start_marker = "*** START OF THE PROJECT GUTENBERG EBOOK"
            end_marker = "*** END OF THE PROJECT GUTENBERG EBOOK"
            
            start_idx = text.find(start_marker)
            end_idx = text.find(end_marker)
            
            if start_idx != -1 and end_idx != -1:
                text = text[start_idx:end_idx]
            
            text = re.sub(r'\s+', ' ', text)
            text = text.strip()
            
            return text
        else:
            print(f"   Failed to download {title} (Status: {response.status_code})")
            return None
    except Exception as e:
        print(f"   Error downloading {title}: {e}")
        return None

def split_into_chapters(text, title):
    chapter_patterns = [
        r'CHAPTER\s+[IVX\d]+',
        r'Chapter\s+[IVX\d]+',
        r'CHAPTER\s+[A-Z]+',
        r'Chapter\s+[A-Z]+'
    ]
    
    chapters = []
    current_chapter = ""
    
    lines = text.split('\n')
    for line in lines:
        is_chapter_start = False
        for pattern in chapter_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                if current_chapter.strip():
                    chapters.append(current_chapter.strip())
                current_chapter = line + " "
                is_chapter_start = True
                break
        
        if not is_chapter_start:
            current_chapter += line + " "
    
    if current_chapter.strip():
        chapters.append(current_chapter.strip())
    
    if len(chapters) <= 1:
        words = text.split()
        chunk_size = 1000 
        chapters = []
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i+chunk_size])
            chapters.append(f"Section {i//chunk_size + 1}: {chunk}")
    
    return chapters


all_documents = []

for book_info in books_to_download:
    book_text = download_gutenberg_book(
        book_info["id"], 
        book_info["title"], 
        book_info["author"], 
        book_info["genre"]
    )
    
    if book_text:
        chapters = split_into_chapters(book_text, book_info["title"])
        
        print(f"   📖 {book_info['title']}: {len(chapters)} chapters, {len(book_text.split())} words")
        for i, chapter in enumerate(chapters):
            if len(chapter) > 100: 
                doc = {
                    "title": book_info["title"],
                    "author": book_info["author"],
                    "content": chapter,
                    "genre": book_info["genre"],
                    "book_id": str(book_info["id"]),
                    "chapter": f"Chapter {i+1}",
                    "publication_year": 1800 + (book_info["id"] % 200), 
                    "word_count": len(chapter.split())
                }
                all_documents.append(doc)
    else:
        print(f" Skipping {book_info['title']} - download failed")

print(f"downloaded {len(all_documents)}")


for i, doc in enumerate(all_documents):
    es.index(index=INDEX_NAME, id=i+1, body=doc)
    if (i + 1) % 10 == 0:
        print(f"   Uploaded {i+1} chapters...")


time.sleep(3)

def search_by_genre(genre):
    print(f"Searching for {genre}")
    
    query = {
        "query": {
            "term": {
                "genre": genre
            }
        }
    }
    
    try:
        response = es.search(index=INDEX_NAME, body=query, size=5)
        hits = response['hits']['hits']
        
        if hits:
            print(f"Found {response['hits']['total']['value']} {genre} books!")
            for i, hit in enumerate(hits, 1):
                print(f"\n{i}. {hit['_source']['title']} by {hit['_source']['author']}")
                print(f"   Chapter: {hit['_source']['chapter']}")
                print(f"   Word Count: {hit['_source']['word_count']}")
                print(f"   Content Preview: {hit['_source']['content'][:200]}...")
        else:
            print(f"No {genre} books found!")
            
    except Exception as e:
        print(f"Oops! Genre search failed: {e}")

def search_quotes(search_term):
    print(f"Searching for quotes containing: '{search_term}'")
    
    query = {
        "query": {
            "match_phrase": {
                "content": search_term
            }
        },
        "highlight": {
            "fields": {
                "content": {
                    "fragment_size": 150,
                    "number_of_fragments": 2
                }
            }
        }
    }
    
    try:
        response = es.search(index=INDEX_NAME, body=query, size=3)
        hits = response['hits']['hits']
        
        if hits:
            print(f"Found {response['hits']['total']['value']} quotes!")
            for i, hit in enumerate(hits, 1):
                print(f"\n{i}. From '{hit['_source']['title']}' by {hit['_source']['author']}")
                print(f"   Chapter: {hit['_source']['chapter']}")
                print(f"   Score: {hit['_score']:.2f}")
                if 'highlight' in hit and 'content' in hit['highlight']:
                    print(f"   Quote: ...{hit['highlight']['content'][0]}...")
        else:
            print("No quotes found!")
            
    except Exception as e:
        print(f"Oops! Quote search failed: {e}")

def search_by_author(author_name):
    print(f" Searching for books by: {author_name}")
    
    query = {
        "query": {
            "match": {
                "author": author_name
            }
        }
    }
    
    try:
        response = es.search(index=INDEX_NAME, body=query, size=5)
        hits = response['hits']['hits']
        
        if hits:
            print(f"Found {response['hits']['total']['value']} books by {author_name}!")
            for i, hit in enumerate(hits, 1):
                print(f"\n{i}. {hit['_source']['title']}")
                print(f"   Genre: {hit['_source']['genre']}")
                print(f"   Chapter: {hit['_source']['chapter']}")
                print(f"   Word Count: {hit['_source']['word_count']}")
        else:
            print(f"No books found by {author_name}!")
            
    except Exception as e:
        print(f"Oops! Author search failed: {e}")

def search_themes(theme_words):
    print(f"Searching for books about: {', '.join(theme_words)}")
    
    query = {
        "query": {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": " ".join(theme_words),
                            "fields": ["title", "content"]
                        }
                    }
                ]
            }
        },
        "highlight": {
            "fields": {
                "content": {
                    "fragment_size": 200,
                    "number_of_fragments": 1
                }
            }
        }
    }
    
    try:
        response = es.search(index=INDEX_NAME, body=query, size=5)
        hits = response['hits']['hits']
        
        if hits:
            print(f"Found {response['hits']['total']['value']} books discussing these themes!")
            for i, hit in enumerate(hits, 1):
                print(f"\n{i}. {hit['_source']['title']} by {hit['_source']['author']}")
                print(f"   Genre: {hit['_source']['genre']}")
                print(f"   Score: {hit['_score']:.2f}")
                if 'highlight' in hit and 'content' in hit['highlight']:
                    print(f"   Relevant passage: ...{hit['highlight']['content'][0]}...")
        else:
            print("No books found discussing these themes!")
            
    except Exception as e:
        print(f"Oops! Theme search failed: {e}")

def search_long_books(min_words=2000):
    print(f"\Searching for longer chapters (min {min_words} words)...")
    
    query = {
        "query": {
            "range": {
                "word_count": {
                    "gte": min_words
                }
            }
        },
        "sort": [
            {"word_count": {"order": "desc"}}
        ]
    }
    
    try:
        response = es.search(index=INDEX_NAME, body=query, size=5)
        hits = response['hits']['hits']
        
        if hits:
            print(f"Found {response['hits']['total']['value']} long chapters!")
            for i, hit in enumerate(hits, 1):
                print(f"\n{i}. {hit['_source']['title']} by {hit['_source']['author']}")
                print(f"   Chapter: {hit['_source']['chapter']}")
                print(f"   Word Count: {hit['_source']['word_count']}")
                print(f"   Genre: {hit['_source']['genre']}")
        else:
            print(f"No chapters found with {min_words}+ words!")
            
    except Exception as e:
        print(f"Oops! Long book search failed: {e}")

def show_library_stats():
    print("Library Statistics")
    
    count_query = {"query": {"match_all": {}}}
    count_response = es.search(index=INDEX_NAME, body=count_query, size=0)
    total_chapters = count_response['hits']['total']['value']
    
    genre_query = {
        "aggs": {
            "genres": {
                "terms": {
                    "field": "genre",
                    "size": 10
                }
            }
        },
        "size": 0
    }
    
    try:
        genre_response = es.search(index=INDEX_NAME, body=genre_query)
        genres = genre_response['aggregations']['genres']['buckets']
        
        print(f"Total Chapters: {total_chapters}")
        print(f"Total Books: {len(books_to_download)}")
        print("\nGenre Breakdown:")
        for genre in genres:
            print(f"  {genre['key']}: {genre['doc_count']} chapters")
            
    except Exception as e:
        print(f"Couldn't get genre stats: {e}")

if __name__ == "__main__":
    
    show_library_stats()
    
    
    search_by_genre("Adventure")
    search_by_genre("Gothic")

    search_quotes("Call me Ishmael")
    search_quotes("It was the best of times")
    search_quotes("To be or not to be")
    

    search_by_author("Mark Twain")
    search_by_author("Charles Dickens")
    

    search_themes(["love", "death"])
    search_themes(["adventure", "sea"])
    search_themes(["monster", "fear"])
    
    search_long_books(1500)