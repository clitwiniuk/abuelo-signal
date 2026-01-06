#!/bin/bash

# Get token from database
TOKEN=$(psql -d carlos -t -c "SELECT token FROM user_tokens WHERE user_id = '7ab22590-ebff-4cc0-b2c3-43170dda53d2' ORDER BY created_at DESC LIMIT 1" | tr -d ' ')

echo "Testing /api/trades?status=open"
curl -s "http://localhost:3000/api/trades?status=open" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.' || echo "Failed"

echo ""
echo "Testing /api/trades/open-positions-quotes"
curl -s "http://localhost:3000/api/trades/open-positions-quotes" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.' || echo "Failed"
