"""
CURP 画像生成 MCP 客户端：固定调用远程 CURP API，不加载本地模型。

固定地址:
  http://47.116.195.100:13366/api/generate_demographic
"""
import json
from typing import Optional

try:
    import requests
except ImportError:
    requests = None

try:
    from fastmcp import FastMCP
except ImportError:
    FastMCP = None

API_URL = "http://47.116.195.100:13366/api/generate_demographic"


def _call_api(n: int, init_requirement: Optional[str] = None) -> str:
    """调用固定的远程 CURP API，返回 JSON 字符串。"""
    if requests is None:
        return json.dumps(
            {
                "error": "requests not installed",
                "profiles": {},
            },
            ensure_ascii=False,
        )

    payload = {"n": n, "init_requirement": init_requirement}
    try:
        r = requests.post(API_URL, json=payload, timeout=120)
        r.raise_for_status()
        return json.dumps(r.json(), ensure_ascii=False)
    except requests.exceptions.RequestException as e:
        return json.dumps(
            {
                "error": str(e),
                "profiles": {},
            },
            ensure_ascii=False,
        )


if FastMCP is None:

    def main():
        print("Install: pip install fastmcp requests")
        print(
            "This MCP client calls fixed endpoint: "
            "http://47.116.195.100:13366/api/generate_demographic"
        )

else:
    mcp = FastMCP(
        name="CURP Demographic",
        description=(
            "Call fixed CURP demographic API at "
            "http://47.116.195.100:13366/api/generate_demographic "
            "to generate virtual user profiles."
        ),
    )

    @mcp.tool(
        name="curp_generate_demographic",
        description=(
            "Generate N virtual user demographic profiles by calling the fixed "
            "CURP API endpoint. Optional init_requirement (in English) "
            "constrains the profiles, e.g. 'Occupations should be game-related.' "
            "Returns JSON with a 'profiles' object."
        ),
    )
    def curp_generate_demographic(
        n: int = 10,
        init_requirement: Optional[str] = None,
    ) -> str:
        """
        Generate N demographic profiles.

        - n: number of profiles (1–32; the remote API itself supports up to 1000).
        - init_requirement: optional English constraint that the backend injects
          into the prompt.
        """
        n = max(1, min(32, n))
        return _call_api(n=n, init_requirement=init_requirement)

    def main():
        mcp.run()


if __name__ == "__main__":
    main()