const axios = require('axios');

async function testCommentsEndpoint() {
  try {
    console.log('Testing comments endpoint...');

    // Test without auth (should work if trade is public or fail gracefully)
    const response = await axios.get('http://localhost:3000/api/trades/48985/comments');

    console.log('Success! Response:', response.data);
  } catch (error) {
    console.error('Error:', error.response?.status, error.response?.statusText);
    console.error('Error data:', error.response?.data);
    console.error('Full error:', error.message);
  }
}

testCommentsEndpoint();
