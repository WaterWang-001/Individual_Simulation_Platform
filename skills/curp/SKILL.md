---
name: curp-demographic
description: Generates virtual user demographic profiles by calling the deployed CURP API via MCP tool curp_generate_demographic. Use when the user asks for demographic profiles, user personas, diverse user descriptions, or constrained profiles (e.g. game-related occupations, tech interests). Use only for profile generation, not for answer generation.
---

# CURP Demographic Profile Generation

## When to use

- User asks for virtual user **demographic profiles**, **personas**, or **diverse user descriptions**.
- User wants **constrained** profiles (e.g. occupations game-related, tech interests, formal communication style)—express the constraint in **English** as `init_requirement`.
- Do **not** use for “answer as this user”; this skill only produces profile text.

## Instructions

1. Confirm the request is **profile-only** (no answer generation).
2. If there is a constraint (occupation, interests, style), phrase it in **one short English sentence** for `init_requirement`.
3. Call the MCP tool **curp_generate_demographic** with:
   - `n`: number of profiles (1–32).
   - `init_requirement`: optional English constraint, or omit for random profiles.
4. Parse the returned JSON and present the **profiles** to the user. `profiles` is an object: keys are string indices (`"0"`, `"1"`, …), values are profile text strings.

> Implementation note: the MCP tool calls the fixed HTTP endpoint `http://47.116.195.100:13366/api/generate_demographic`.

## Tool parameters

| Parameter | Type | Default | Meaning |
|-----------|------|---------|---------|
| `n` | int | 10 | Number of profiles (1–32). |
| `init_requirement` | str \| null | null | Optional English constraint, injected into the model prompt. |

Return value: JSON string with `profiles` (object mapping string index to profile text). The API does not return indices.

## Examples

**Random profiles (no constraint)**

- `curp_generate_demographic(n=20)`

**Game-related occupations**

- `curp_generate_demographic(n=10, init_requirement="Occupations should be game-related.")`

**Tech-related interests**

- `curp_generate_demographic(n=5, init_requirement="Interests should be related to technology and gadgets.")`

**Formal communication style**

- `curp_generate_demographic(n=8, init_requirement="Communication style should be formal and professional.")`
