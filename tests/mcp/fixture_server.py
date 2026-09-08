"""Real SDK fixture for both stdio and in-process HTTP transport tests."""
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

mcp = FastMCP('fixture', stateless_http=True, json_response=True)


class Item(BaseModel):
    name: str
    count: int


@mcp.tool()
def total(items: list[Item]) -> dict[str, int]:
    """Sum counts in nested structured arguments."""
    return {'total': sum(item.count for item in items)}


@mcp.tool()
def fail() -> str:
    """Return a real MCP tool error."""
    raise ValueError('fixture rejected the operation')


if __name__ == '__main__':
    mcp.run(transport='stdio')
