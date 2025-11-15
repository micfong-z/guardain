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

    async def process_query(self) -> str:

        current_time = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(time.time()))
        latitude = 52.20641
        '''记得删掉！CHANGES_REQUIRED'''
        longitude = 0.12185
        '''记得删掉！CHANGES_REQUIRED'''

        CLAUDE_PROMPT= f"""Time = {current_time}, Latitude = {latitude}, Longitude = {longitude}
                        You are a Regional Safety Assessment Assistant. Provide objective safety risk assessments based on user's time and location. Follow the exact workflow. Output ONLY the final assessment in the specified format.
                        
                        Workflow
                        Step 1: Weather Query (ALWAYS)
                        Call Tool2 immediately upon receiving location.
                        
                        Step 2: Crime Data Query (CONDITIONAL)
                            Call Tool1 if ANY condition met:
                                Time is 20:00-06:00 (night)
                                Severe weather (heavy rain/fog/snow, visibility <1km)
                                User explicitly requests assessment
                        
                        Step 3: Calculate Risk Index (if Tool1 called)
                            Crime Scores:
                            Violent/Robbery: 9 | Burglary/Weapons: 7 | Vehicle/Pickpocketing: 5 | Minor theft: 3 | Anti-social: 2
                            Time Decay:
                            ≤1mo: ×1.0 | 2-3mo: ×0.75 | 4-6mo: ×0.5 | >6mo: ×0.25
                            Formula:
                                Incident_Score = Crime_Score × Time_Decay
                                Average_Score = Σ(Incident_Score) / Total_Incidents
                                Density_Coeff = [1.0 (≤5), 1.2 (6-15), 1.4 (16-30), 1.6 (>30)]
                                Preliminary_RI = Average_Score × Density_Coeff
                                Environment_Modifier = [1.0 (day+good), 1.2 (night), 1.15 (bad weather), 1.38 (both)]
                                Final_RI = Preliminary_RI × Environment_Modifier
                        
                        Step 4: Classify & Act
                            Levels:
                            1 (Low): 0-2.5 | 2 (Lower): 2.5-5.0 | 3 (Moderate): 5.0-7.5 | 4 (Higher): 7.5-10.0 | 5 (High): ≥10.0
                            Action:
                                Conclude a reason why it is dangerous or not, no more than 50 words in total.
                        Step 5: Output Format
                            [1,5] (INCLUDE ONLY:Integer of level)
                            Reason:
                        
                        
                        NEVER INCLUDE:
                            Tool call descriptions: [Calling tool...]
                            Conversational text
                            Methodology explanations
                            Disclaimers or apologies
                            Safety advice (unless level ≥4)
                            Assumptions or inferences
                            Step1&2&3&4s' process
                            
        
                        Error Handling
                        If tool fails:
                        【Safety Assessment】
                        Status: Unable to complete assessment
                        Reason: [Tool name] data unavailable
                        Location: [Area]
                        Time: [YYYY-MM-DD HH:MM]
                        Core Principles
                        
                        Data-driven only
                        Exact format compliance
                        No extraneous content
                        Privacy protection
                        Neutral language"""

        messages = [
            {
                "role": "user",
                "content": CLAUDE_PROMPT
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

    async def chat(self):
        try:
            response = await self.process_query()
        except Exception as e:
            print(f"\nError: {str(e)}")

        return response

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()


async def get_danger_and_description():
    client = MCPClient()
    await client.connect_to_server('MCP_server.py')
    response = await client.chat()
    lines = response.split('\n')
    # Continuously remove blank lines until no further element to be removed
    try:
        while True:
            lines.remove('')
    except:
        pass

    """
    Format of lines：
    xxx xxx
    a digit of danger level
    an explanation on why
    """

    while not lines[-2].isdigit():
        print("\033[34mWrong format, retrying...\033[0m")
        response = await client.chat()
        lines = response.split('\n')
        lines.remove('')

    danger_level = int(lines[-2])
    reason = lines[-1]
    for kwreason in ['Reason:','Reasons:','reason:','reasons:']:
        reason = reason.replace(kwreason,'').lstrip()

    await client.cleanup()

    print(response)
    '''记得删掉！CHANGES_REQUIRED'''

    return (danger_level, reason)


if __name__ == "__main__":
    asyncio.run(get_danger_and_description())