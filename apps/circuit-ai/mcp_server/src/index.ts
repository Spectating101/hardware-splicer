#!/usr/bin/env node

/**
 * Circuit-AI MCP Server
 *
 * Provides professional PCB validation, project recipes, and manufacturing tools
 * via Model Context Protocol (MCP).
 *
 * Tools:
 * - validate-kicad: Professional PCB validation with quantitative fixes
 * - suggest-projects: Get buildable projects from inventory
 * - calculate-roi: Economics and ROI for projects
 * - generate-bom: Generate bill of materials
 * - get-build-instructions: Step-by-step build guides
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from "@modelcontextprotocol/sdk/types.js";
import axios from "axios";
import FormData from "form-data";
import fs from "fs";

// Configuration
const API_BASE_URL = process.env.CIRCUIT_AI_API_URL || "http://localhost:5000";
const API_KEY = process.env.CIRCUIT_AI_API_KEY || "";

// Tool definitions
const TOOLS: Tool[] = [
  {
    name: "validate-kicad",
    description: "Validate KiCAD PCB design with quantitative fixes. Checks power tree, trace drops, LDO regulation. Returns physics-based issues with exact measurements (e.g., 'Widen trace to 2mm').",
    inputSchema: {
      type: "object",
      properties: {
        netlist_path: {
          type: "string",
          description: "Path to KiCAD .net file (S-expression netlist)",
        },
        hints: {
          type: "object",
          description: "Optional hints for validation (sources, loads, voltage constraints)",
          properties: {
            sources: {
              type: "array",
              description: "Power sources (e.g., USB, battery)",
              items: {
                type: "object",
                properties: {
                  name: { type: "string" },
                  net: { type: "string" },
                  volts: { type: "number" },
                  max_current_a: { type: "number" },
                },
              },
            },
            loads_cc: {
              type: "array",
              description: "Constant current loads (ICs, modules)",
              items: {
                type: "object",
                properties: {
                  name: { type: "string" },
                  net: { type: "string" },
                  amps: { type: "number" },
                },
              },
            },
            voltage_constraints: {
              type: "array",
              description: "Voltage requirements for rails",
              items: {
                type: "object",
                properties: {
                  net: { type: "string" },
                  min_v: { type: "number" },
                  max_v: { type: "number" },
                },
              },
            },
          },
        },
      },
      required: ["netlist_path"],
    },
  },
  {
    name: "suggest-projects",
    description: "Get buildable project recommendations based on inventory. Returns projects with ROI calculations, cost estimates, and inventory match percentage.",
    inputSchema: {
      type: "object",
      properties: {
        inventory: {
          type: "array",
          description: "List of components you have",
          items: {
            type: "object",
            properties: {
              id: {
                type: "string",
                description: "Component ID (e.g., 'esp32', 'arduino_uno', 'bme280')",
              },
              condition: {
                type: "string",
                enum: ["new", "used", "scrap"],
                description: "Component condition",
              },
              quantity: {
                type: "number",
                description: "How many you have",
              },
            },
            required: ["id", "condition", "quantity"],
          },
        },
        skill_level: {
          type: "number",
          enum: [1, 2, 3, 4, 5],
          description: "User skill level (1=beginner, 2=hobbyist, 3=intermediate, 4=advanced, 5=professional)",
          default: 2,
        },
        goal: {
          type: "string",
          enum: ["learning", "roi", "speed"],
          description: "What you're optimizing for",
          default: "learning",
        },
        budget: {
          type: "number",
          description: "Maximum budget for missing parts (USD)",
          default: 50,
        },
      },
      required: ["inventory"],
    },
  },
  {
    name: "calculate-roi",
    description: "Calculate ROI and economics for a specific project. Returns parts cost, market price range, profit margin, and ROI percentage.",
    inputSchema: {
      type: "object",
      properties: {
        project_name: {
          type: "string",
          description: "Name of the project (e.g., 'Air Quality Monitor')",
        },
        inventory: {
          type: "array",
          description: "Components you already have",
          items: {
            type: "object",
            properties: {
              id: { type: "string" },
              condition: { type: "string" },
              quantity: { type: "number" },
            },
          },
        },
      },
      required: ["project_name"],
    },
  },
  {
    name: "generate-bom",
    description: "Generate bill of materials (BOM) from KiCAD netlist. Returns component list with part numbers, quantities, and supplier links.",
    inputSchema: {
      type: "object",
      properties: {
        netlist_path: {
          type: "string",
          description: "Path to KiCAD .net file",
        },
        include_pricing: {
          type: "boolean",
          description: "Include real-time pricing from DigiKey",
          default: false,
        },
      },
      required: ["netlist_path"],
    },
  },
  {
    name: "get-build-instructions",
    description: "Get step-by-step build instructions for a project. Returns detailed assembly guide with wiring diagrams, code, and troubleshooting tips.",
    inputSchema: {
      type: "object",
      properties: {
        project_name: {
          type: "string",
          description: "Name of the project",
        },
      },
      required: ["project_name"],
    },
  },
  {
    name: "generate-gerber",
    description: "Generate Gerber files from KiCAD PCB for manufacturing. Returns Gerber ZIP package ready for JLCPCB/OSH Park/PCBWay with cost estimates.",
    inputSchema: {
      type: "object",
      properties: {
        pcb_path: {
          type: "string",
          description: "Path to KiCAD .kicad_pcb file",
        },
        quantity: {
          type: "number",
          description: "PCB quantity for cost estimation (default: 5)",
          default: 5,
        },
      },
      required: ["pcb_path"],
    },
  },
  {
    name: "get-jlcpcb-quote",
    description: "Get JLCPCB price quote and ordering instructions for PCB manufacturing. Returns detailed cost breakdown and order URL.",
    inputSchema: {
      type: "object",
      properties: {
        width_mm: {
          type: "number",
          description: "PCB width in mm",
        },
        height_mm: {
          type: "number",
          description: "PCB height in mm",
        },
        layers: {
          type: "number",
          enum: [2, 4, 6],
          description: "Number of layers (2, 4, or 6)",
        },
        quantity: {
          type: "number",
          description: "Number of PCBs to order (default: 5)",
          default: 5,
        },
        surface_finish: {
          type: "string",
          enum: ["HASL", "LeadFree HASL", "ENIG"],
          description: "Surface finish type (default: LeadFree HASL)",
          default: "LeadFree HASL",
        },
      },
      required: ["width_mm", "height_mm", "layers"],
    },
  },
];

// API client helpers
class CircuitAIClient {
  private baseURL: string;
  private apiKey: string;

  constructor(baseURL: string, apiKey: string) {
    this.baseURL = baseURL;
    this.apiKey = apiKey;
  }

  private getHeaders() {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (this.apiKey) {
      headers["Authorization"] = `Bearer ${this.apiKey}`;
    }
    return headers;
  }

  async validateKiCAD(netlistPath: string, hints?: any): Promise<any> {
    // Check if file exists
    if (!fs.existsSync(netlistPath)) {
      throw new Error(`File not found: ${netlistPath}`);
    }

    // Use multipart form data for file upload
    const formData = new FormData();
    formData.append("kicad_file", fs.createReadStream(netlistPath));
    if (hints) {
      formData.append("hints", JSON.stringify(hints));
    }

    const response = await axios.post(
      `${this.baseURL}/api/v2/workflow/validate-kicad`,
      formData,
      {
        headers: {
          ...formData.getHeaders(),
          ...(this.apiKey && { Authorization: `Bearer ${this.apiKey}` }),
        },
      }
    );

    return response.data;
  }

  async suggestProjects(params: any): Promise<any> {
    const response = await axios.post(
      `${this.baseURL}/api/v2/workflow/beginner`,
      params,
      { headers: this.getHeaders() }
    );

    return response.data;
  }

  async calculateROI(projectName: string, inventory?: any[]): Promise<any> {
    const response = await axios.post(
      `${this.baseURL}/api/v2/workflow/complete`,
      {
        user: {
          skill_level: 2,
          inventory: inventory || [],
          goal: "roi",
        },
        project_name: projectName,
      },
      { headers: this.getHeaders() }
    );

    return response.data;
  }

  async generateBOM(netlistPath: string, includePricing: boolean): Promise<any> {
    // Check if file exists
    if (!fs.existsSync(netlistPath)) {
      throw new Error(`File not found: ${netlistPath}`);
    }

    // Use multipart form data for file upload
    const formData = new FormData();
    formData.append("netlist_file", fs.createReadStream(netlistPath));
    formData.append("include_pricing", includePricing.toString());
    formData.append("format", "json");

    const response = await axios.post(
      `${this.baseURL}/api/v2/manufacture/bom`,
      formData,
      {
        headers: {
          ...formData.getHeaders(),
          ...(this.apiKey && { Authorization: `Bearer ${this.apiKey}` }),
        },
      }
    );

    return response.data;
  }

  async getBuildInstructions(projectName: string): Promise<any> {
    const response = await axios.get(
      `${this.baseURL}/api/instructions/${encodeURIComponent(projectName)}`,
      { headers: this.getHeaders() }
    );

    return response.data;
  }

  async generateGerber(pcbPath: string, quantity: number = 5): Promise<any> {
    const response = await axios.post(
      `${this.baseURL}/api/v2/manufacture/gerber`,
      { pcb_path: pcbPath, quantity },
      { headers: this.getHeaders() }
    );

    return response.data;
  }

  async getJLCPCBQuote(params: any): Promise<any> {
    // For now, we'll use local JLCPCB integration
    // In production, this would call a dedicated API endpoint
    const {
      width_mm,
      height_mm,
      layers,
      quantity = 5,
      surface_finish = "LeadFree HASL",
    } = params;

    // Simplified pricing calculation (matches jlcpcb_integration.py logic)
    const basePrices: any = {
      2: { 5: 2.0, 10: 2.0, 20: 5.0, 50: 15.0, 100: 25.0 },
      4: { 5: 7.0, 10: 8.0, 20: 15.0, 50: 50.0, 100: 80.0 },
      6: { 5: 25.0, 10: 35.0, 20: 60.0, 50: 150.0, 100: 250.0 },
    };

    let price = basePrices[layers]?.[quantity] || quantity * 0.5;

    // Size multiplier
    const areaCm2 = (width_mm / 10) * (height_mm / 10);
    if (areaCm2 > 100) {
      price *= (areaCm2 / 100) * 1.2;
    }

    // Surface finish multiplier
    if (surface_finish === "ENIG") {
      price *= 2.0;
    } else if (surface_finish === "LeadFree HASL") {
      price *= 1.2;
    }

    const leadTime = quantity <= 10 ? 2 : quantity <= 50 ? 3 : 5;

    return {
      quantity,
      price_usd: parseFloat(price.toFixed(2)),
      unit_price_usd: parseFloat((price / quantity).toFixed(2)),
      lead_time_days: leadTime,
      shipping_options: [
        { method: "Standard", price_usd: 5.0, days: "7-15" },
        { method: "Express", price_usd: 15.0, days: "3-5" },
        { method: "DHL", price_usd: 25.0, days: "2-3" },
      ],
      total_with_standard_shipping: parseFloat((price + 5.0).toFixed(2)),
      order_url: `https://cart.jlcpcb.com/quote?boardWidth=${width_mm}&boardHeight=${height_mm}&boardLayers=${layers}`,
    };
  }
}

// Create server
const server = new Server(
  {
    name: "circuit-ai",
    version: "0.4.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

const client = new CircuitAIClient(API_BASE_URL, API_KEY);

// List available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: TOOLS,
  };
});

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case "validate-kicad": {
        const { netlist_path, hints } = args as {
          netlist_path: string;
          hints?: any;
        };
        const result = await client.validateKiCAD(netlist_path, hints);

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case "suggest-projects": {
        const result = await client.suggestProjects(args);

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case "calculate-roi": {
        const { project_name, inventory } = args as {
          project_name: string;
          inventory?: any[];
        };
        const result = await client.calculateROI(project_name, inventory);

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case "generate-bom": {
        const { netlist_path, include_pricing } = args as {
          netlist_path: string;
          include_pricing?: boolean;
        };
        const result = await client.generateBOM(
          netlist_path,
          include_pricing || false
        );

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case "get-build-instructions": {
        const { project_name } = args as { project_name: string };
        const result = await client.getBuildInstructions(project_name);

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case "generate-gerber": {
        const { pcb_path, quantity } = args as {
          pcb_path: string;
          quantity?: number;
        };
        const result = await client.generateGerber(pcb_path, quantity || 5);

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case "get-jlcpcb-quote": {
        const result = await client.getJLCPCBQuote(args);

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error: any) {
    return {
      content: [
        {
          type: "text",
          text: `Error: ${error.message}\n\nDetails: ${
            error.response?.data
              ? JSON.stringify(error.response.data, null, 2)
              : error.stack
          }`,
        },
      ],
      isError: true,
    };
  }
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);

  console.error("Circuit-AI MCP Server running");
  console.error(`API URL: ${API_BASE_URL}`);
  console.error(`API Key: ${API_KEY ? "configured" : "not configured"}`);
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
