# Simple Document Search Engine

A beginner-friendly Elasticsearch project that demonstrates document storage and search capabilities.

## What This Does

This project creates a simple search engine that:

- Stores 100 fake documents in Elasticsearch
- Demonstrates different types of searches
- Shows how to search across multiple fields
- Implements complex boolean queries

## Quick Start

1. **Start the services:**

   ```bash
   docker-compose up --build
   ```

2. **Watch the magic happen!** The Python script will automatically:

   - Connect to Elasticsearch
   - Create an index
   - Generate and store 100 fake documents
   - Run various search experiments

3. **Access Elasticsearch directly (optional):**
   - Open http://localhost:9200 in your browser
   - You can see the cluster info and run queries

## What You'll Learn

- How to connect to Elasticsearch
- How to create indexes and mappings
- How to store documents
- How to perform basic searches
- How to search across multiple fields
- How to use boolean queries for complex searches

## Project Structure

```
elastic-search/
├── docker-compose.yml    # Docker services configuration
├── Dockerfile           # Python app container
├── requirements.txt     # Python dependencies
├── search_engine.py     # Main application
└── README.md           # This file
```

## Stopping the Services

Press `Ctrl+C` to stop the services, or run:

```bash
docker-compose down
```

## Next Steps

Try modifying the search queries in `search_engine.py` to experiment with different search terms and see what results you get!
