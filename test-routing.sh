#!/bin/bash

echo "Testing enhanced routing rules for LiteLLM Bedrock Proxy"
echo "======================================================"

# First, let's check if the proxy is running
echo "1. Checking proxy status:"
curl -s http://localhost:4000/health/liveliness

echo ""
echo "2. Testing Simple Complexity (should route to qwen3-coder):"
echo "   Request: 'Hello'"
curl -s -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "bedrock-auto",
    "messages": [{"role": "user", "content": "Hello"}]
  }' | jq -r '.choices[0].message.content' | head -c 50

echo ""
echo "3. Testing Medium Complexity (should route to claude-haiku):"
echo "   Request: 'Compare Redis and Memcached'"
curl -s -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "bedrock-auto",
    "messages": [{"role": "user", "content": "Compare Redis and Memcached"}]
  }' | jq -r '.choices[0].message.content' | head -c 50

echo ""
echo "4. Testing Complex Complexity (should route to claude-sonnet):"
echo "   Request: 'Design a microservices architecture for a payment system'"
curl -s -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "bedrock-auto",
    "messages": [{"role": "user", "content": "Design a microservices architecture for a payment system"}]
  }' | jq -r '.choices[0].message.content' | head -c 50

echo ""
echo "5. Testing Coding Request (should route to qwen3-coder):"
echo "   Request: 'Refactor this function to use a more efficient algorithm'"
curl -s -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "bedrock-auto",
    "messages": [{"role": "user", "content": "Refactor this function to use a more efficient algorithm"}]
  }' | jq -r '.choices[0].message.content' | head -c 50

echo ""
echo "All tests completed. Check the responses to see which models were selected."