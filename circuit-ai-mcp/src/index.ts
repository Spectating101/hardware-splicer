#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

// Configure the API base URL - change this when deployed
const API_BASE_URL = process.env.CIRCUIT_AI_API_URL || "http://localhost:5000";

// Create the MCP server
const server = new Server(
  {
    name: "circuit-ai",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Define available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "diagnose_device",
        description:
          "Diagnose device issues from symptoms. Returns possible issues with confidence scores and repair recommendations.",
        inputSchema: {
          type: "object",
          properties: {
            symptoms: {
              type: "array",
              items: { type: "string" },
              description:
                "List of symptoms (e.g., 'battery drains fast', 'screen flickering', 'won't charge')",
            },
            device_type: {
              type: "string",
              description:
                "Type of device (e.g., 'iPhone', 'Samsung', 'Laptop')",
            },
          },
          required: ["symptoms"],
        },
      },
      {
        name: "get_repair_guide",
        description:
          "Get a step-by-step repair guide for a specific issue. Includes tools needed, parts list, safety warnings, and detailed instructions.",
        inputSchema: {
          type: "object",
          properties: {
            issue_name: {
              type: "string",
              description:
                "The issue to get a guide for (e.g., 'iPhone Battery Replacement', 'Laptop Screen Replacement')",
            },
            preview: {
              type: "boolean",
              description:
                "If true, returns only first 3 steps (free preview). Default: false",
            },
          },
          required: ["issue_name"],
        },
      },
      {
        name: "validate_circuit",
        description:
          "Validate a circuit design for common issues like power mismatches, missing connections, or component incompatibilities.",
        inputSchema: {
          type: "object",
          properties: {
            components: {
              type: "array",
              items: {
                type: "object",
                properties: {
                  id: { type: "string" },
                  type: { type: "string" },
                  value: { type: "string" },
                },
              },
              description: "List of circuit components",
            },
            connections: {
              type: "array",
              items: {
                type: "object",
                properties: {
                  from: { type: "string" },
                  to: { type: "string" },
                },
              },
              description: "List of connections between components",
            },
          },
          required: ["components"],
        },
      },
      {
        name: "list_repair_guides",
        description:
          "List all available repair guides with their difficulty levels and time estimates.",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
      {
        name: "generate_project_recipe",
        description:
          "Generate a project recipe from available components/inventory. Suggests what you can build and provides instructions.",
        inputSchema: {
          type: "object",
          properties: {
            inventory: {
              type: "array",
              items: { type: "string" },
              description:
                "List of components you have (e.g., 'ESP32', '10k resistor', 'LED')",
            },
            project_type: {
              type: "string",
              description:
                "Type of project you want to build (e.g., 'sensor', 'display', 'automation')",
            },
          },
          required: ["inventory"],
        },
      },
    ],
  };
});

// Handle tool execution
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case "diagnose_device": {
        const response = await fetch(`${API_BASE_URL}/api/diagnose`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            symptoms: args?.symptoms || [],
            device_type: args?.device_type || "unknown",
          }),
        });

        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(data, null, 2),
            },
          ],
        };
      }

      case "get_repair_guide": {
        const issueName = encodeURIComponent(args?.issue_name || "");
        const preview = args?.preview ? "?preview=true" : "";
        const response = await fetch(
          `${API_BASE_URL}/api/repair-guides/${issueName}${preview}`
        );

        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(data, null, 2),
            },
          ],
        };
      }

      case "validate_circuit": {
        const response = await fetch(`${API_BASE_URL}/api/validate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            components: args?.components || [],
            connections: args?.connections || [],
          }),
        });

        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(data, null, 2),
            },
          ],
        };
      }

      case "list_repair_guides": {
        const response = await fetch(`${API_BASE_URL}/api/repair-guides`);

        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(data, null, 2),
            },
          ],
        };
      }

      case "generate_project_recipe": {
        const response = await fetch(`${API_BASE_URL}/api/recipes/generate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            inventory: args?.inventory || [],
            project_type: args?.project_type,
          }),
        });

        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(data, null, 2),
            },
          ],
        };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : "Unknown error";
    return {
      content: [
        {
          type: "text",
          text: `Error: ${errorMessage}`,
        },
      ],
      isError: true,
    };
  }
});

// Start the server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Circuit-AI MCP Server running on stdio");
}

main().catch(console.error);
