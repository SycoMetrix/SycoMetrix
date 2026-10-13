# API Usage Documentation

## Example: NVIDIA: Nemotron 3 Ultra (free)

Link: nvidia/nemotron-3-ultra-550b-a55b:free

1. Get an API Key

2. Make a request
```py
import requests
import json

# First API call with reasoning
response = requests.post(
  url="https://openrouter.ai/api/v1/chat/completions",
  headers={
    "Authorization": "Bearer <OPENROUTER_API_KEY>",
    "Content-Type": "application/json",
  },
  data=json.dumps({
    "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
    "messages": [
        {
          "role": "user",
          "content": "How many r's are in the word 'strawberry'?"
        }
      ],
    "reasoning": {"enabled": True}
  })
)

# Extract the assistant message with reasoning_details
response = response.json()
response = response['choices'][0]['message']

# Preserve the assistant message with reasoning_details
messages = [
  {"role": "user", "content": "How many r's are in the word 'strawberry'?"},
  {
    "role": "assistant",
    "content": response.get('content'),
    "reasoning_details": response.get('reasoning_details')  # Pass back unmodified
  },
  {"role": "user", "content": "Are you sure? Think carefully."}
]

# Second API call - model continues reasoning from where it left off
response2 = requests.post(
  url="https://openrouter.ai/api/v1/chat/completions",
  data=json.dumps({
    "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
    "messages": messages,  # Includes preserved reasoning_details
    "reasoning": {"enabled": True}
  })
)
```

3. Enable Streaming
```py
curl -N https://openrouter.ai/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -d '{
  "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
  "stream": true,
  "messages": [
    {"role": "user", "content": "Hello"}
  ]
}
```

### Response:
| <span style="color:#34dfaa">POST</span> | <span style="color:hsl(240 50% 99.2% / .627)">https://openrouter.ai/api/v1/messages</span> |
| ---- | ---- |
| <span style="color:white">`Authorization`</span> | Bearer $OPENROUTER_API_KEY |
| <span style="color:white">`Content-Type`</span> | application/json |
| <span style="color:white">`HTTP-Referer`</span> | optional — your site URL, for rankings |
| <span style="color:white">`X-Title`</span> | optional — your site name, for rankings |
| <span style="color:white">`Model`</span> | nvidia/nemotron-3-ultra-550b-a55b:free |

### Parameters
| Name | Type | Default | Description |
|------|------|---------|-------------|
| <span style="color:white">`reasoning`</span> | map | — | Controls reasoning behavior for models that support thinking tokens, including whether reasoning is enabled, the reasoning effort, maximum reasoning tokens, and whether reasoning is excluded from the response. |
| <span style="color:white">`temperature`</span> | float | `1` | This setting influences the variety in the model's responses. |
| <span style="color:white">`max_tokens`</span> | integer | — | This sets the upper limit for the number of tokens the model can generate in response. |
| <span style="color:white">`seed`</span> | integer | — | If specified, the inferencing will sample deterministically, such that repeated requests with the same seed and parameters should return the same result. |
| <span style="color:white">`top_p`</span> | float | `0.95` | This setting limits the model's choices to a percentage of likely tokens: only the top tokens whose probabilities add up to P. |
| <span style="color:white">`tools`</span> | array | — | Tool calling parameter, following OpenAI's tool calling request shape. |
| <span style="color:white">`tool_choice`</span> | string or object | — | Controls which (if any) tool is called by the model. |