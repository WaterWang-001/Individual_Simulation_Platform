# CURP Demographic — MCP Server

## Server

- **Name**: CURP Demographic
- **Description**: Calls a deployed CURP demographic API over HTTP to generate virtual user profiles. No local model loading.

## Installation

```bash
pip install -r requirements-mcp.txt
```

Dependencies: `fastmcp`, `requests`.

## Configuration

### MCP configuration (e.g. Cursor / mcp.json)

```json
{
  "mcpServers": {
    "curp-demographic": {
      "command": "python",
      "args": ["/path/to/curp_demo/curp_demographic_mcp.py"]
    }
  }
}
```

For stdio transport, `command` and `args` must point to the Python interpreter and the script path.

## Tools

### curp_generate_demographic

Generates N virtual user demographic profiles by calling the deployed CURP API. Optional English constraint (e.g. occupations game-related) can be passed as `init_requirement`.

**Input schema**

```json
{
  "type": "object",
  "properties": {
    "n": {
      "type": "integer",
      "default": 10,
      "minimum": 1,
      "maximum": 32,
      "description": "Number of profiles to generate (MCP tool caps at 32; API supports 1–1000)."
    },
    "init_requirement": {
      "type": ["string", "null"],
      "default": null,
      "description": "Optional constraint for the profiles in English (e.g. 'Occupations should be game-related.'). Injected into the model prompt."
    }
  }
}
```

**Result**

JSON string with the API response. Success example:

```json
{
  "profiles": {
    "0": "First profile text...",
    "1": "Second profile text..."
  }
}
```

`profiles` is an object: keys are string indices (`"0"`, `"1"`, …), values are profile text strings. The API does not return `indices`.

On error, the response may include `error` and an empty or missing `profiles`.

## Run (stdio)

```bash
python curp_demographic_mcp.py
```

Or with FastMCP CLI:

```bash
fastmcp run curp_demographic_mcp.py
```

The MCP client calls the fixed HTTP endpoint:

```bash
curl -X POST "http://47.116.195.100:13366/api/generate_demographic" \
  -H "Content-Type: application/json" \
  -d '{
    "n": 10,
    "init_requirement": null
  }'
```
