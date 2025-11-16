import asyncio
import os
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from anthropic import Anthropic
from dotenv import load_dotenv

import time

load_dotenv()  # load environment variables from .env


class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=os.environ.copy()
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        #print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def process_query(self, latitude: float, longitude: float) -> str:

        current_time = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(time.time()))

        SYSTEM_PROMPT = f"""You are a Regional Safety Assessment Assistant integrated with MCP tools.
                                1) OUTPUT CONTROL
                                   - FINAL THREE LINES MUST BE:
                                        <Line 1> an integer 1–5 (the safety level)
                                        <Line 2> a decimal value representing RI (no units)
                                        <Line 3> Reason: <≤50 words>
                                   
                                2) WORKFLOW
                                    STEP 1: call Crime Tool
                                    STEP 2: call Weather Tool
                                    STEP 3: classify Safety level
                                    STEP 4: Generate reasoning
                                    STEP 5: OUTPUT:
                                        <Line 1> integer 1–5
                                        <Line 2> The value of Final_RI
                                        <Line 3> Reason: <≤50 words>
                                            
                                3) TOOL CALL RESTRICTIONS
                                   - You may ONLY call these tools:
                                       • Weather Tool (get_weather_conditions)
                                       • Crime Tool (get_crime_summary)
                                   - You MUST NOT call any other tool (e.g., time_context, location_info, etc.).

                                4) FINAL OUTPUT FORMAT (STRICT)
                                   After all tools have returned, output EXACTLY these three lines:
                                       <Line 1> an integer 1–5 (the safety level)
                                       <Line 2> a decimal value representing Final_RI (no units)
                                       <Line 3> Reason: <≤50 words>

                                   - NO brackets
                                   - NO labels other than the word "Reason:"
                                   - NO bullet points
                                   - NO additional text or whitespace
                                   - NO explanations, disclaimers, or formulas

                                5) RI Classification:
                                    Using the data get from crime tool and weather tool, ANALYZE and classify it into 5 level,from the safest level1 to the most dangerous level5. 
                                    MUST give an INTEGER FROM 1 TO 5
                                    REFERENCE FOLLOWING EXAMPLES:
                                        LEVEL 1: RI = 1000
                                        LEVEL 2: RI = 3000
                                        LEVEL 3: RI = 5000
                                        LEVEL 4: RI = 6000
                                        LEVEL 5: RI = 8000

                                7) REASON RULES
                                   - Provide ≤50 words.
                                    - No workflow references.
                                   - No formulas.
                                   - No assumptions or safety instructions.

                                You must comply perfectly.
                                """

        USER_PROMPT = f"""Time = {current_time}, Latitude = {latitude}, Longitude = {longitude}
                                
                                The FINAL THREE LINES MUST be:
                                   <Line 1> integer 1–5
                                   <Line 2> The value of RI
                                   <Line 3> Reason: <≤50 words>
                                """

        messages = [
            {
                "role": "user",
                "content": USER_PROMPT  # CLAUDE_PROMPT
            }
        ]

        response = await self.session.list_tools()
        available_tools = [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]

        # Initial Claude API call
        response = self.anthropic.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=available_tools
        )

        # Process response and handle tool calls
        final_text = []

        for content in response.content:
            if content.type == 'text':
                final_text.append(content.text)
            elif content.type == 'tool_use':
                tool_name = content.name
                tool_args = content.input

                # Execute tool call
                result = await self.session.call_tool(tool_name, tool_args)
                final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

                # Continue conversation with tool results
                if hasattr(content, 'text') and content.text:
                    messages.append({
                        "role": "assistant",
                        "content": content.text
                    })
                messages.append({
                    "role": "user",
                    "content": result.content
                })

                # Get next response from Claude
                response = self.anthropic.messages.create(
                    model="claude-sonnet-4-5",
                    max_tokens=1000,
                    messages=messages,
                )

                final_text.append(response.content[0].text)

        return "\n".join(final_text)

    async def chat(self, latitude, longitude):
        try:
            response = await self.process_query(latitude=latitude, longitude=longitude)
        except Exception as e:
            print(f"\nError: {str(e)}")

        return response

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()


async def get_danger_and_description(latitude, longitude):
    client = MCPClient()
    await client.connect_to_server('api/MCP_server.py')
    response = await client.chat(latitude, longitude)
    lines = response.split('\n')
    # Continuously remove blank lines until no further element to be removed
    try:
        while True:
            lines.remove('')
    except:
        pass

    while not lines[-3].isdigit():
        print("\033[34mWrong format, retrying...\033[0m")
        response = await client.chat()
        lines = response.split('\n')
        lines.remove('')

    danger_level = int(lines[-3])
    reason = lines[-1]
    for kwreason in ['Reason:','Reasons:','reason:','reasons:']:
        reason = reason.replace(kwreason,'').lstrip()

    await client.cleanup()

    print(response)
    '''记得删掉！CHANGES_REQUIRED'''

    return (danger_level, reason)


if __name__ == "__main__":
    asyncio.run(get_danger_and_description(latitude=51.7548, longitude=-1.2544))