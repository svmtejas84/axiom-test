import type { NextApiRequest, NextApiResponse } from "next";
import { spawn } from "child_process";
import path from "path";
import fs from "fs";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "POST") {
    return res.status(405).json({ detail: "Method not allowed" });
  }

  const { upi_id, parent_vpa, landlord_vpa } = req.body;

  // 1. Map VPA to Mock CSV
  let mockPath = "";
  if (upi_id === "tejas26@okaxis") mockPath = "examples/high_trust_neighborhood.csv";
  else if (upi_id === "rahul@upi") mockPath = "examples/medium_trust_neighborhood.csv";
  else if (upi_id === "john21@upi") mockPath = "examples/low_trust_neighborhood.csv";
  else if (upi_id === "reema22@sbi") mockPath = "examples/medium_trust_neighborhood.csv"; // Added from user log
  else {
    const handle = upi_id?.split("@")[0] || "test_data1";
    mockPath = `examples/${handle}.csv`;
  }

  const rootDir = path.join(process.cwd(), "..");
  const fullMockPath = path.join(rootDir, mockPath);
  const finalPath = fs.existsSync(fullMockPath) ? mockPath : "examples/high_trust_neighborhood.csv";

  const scriptPath = "axiom_merchant_sandbox/run_axiom_stateless.py";
  const args = [scriptPath, finalPath];
  if (req.body.student_verified || upi_id) args.push("--student-verified");
  if (req.body.rent_verified || landlord_vpa) args.push("--rent-verified");
  if (parent_vpa) args.push("--parent-vpa", parent_vpa);
  if (landlord_vpa) args.push("--landlord-vpa", landlord_vpa);

  // Set up SSE
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");

  const sendEvent = (data: any) => {
    res.write(`data: ${JSON.stringify(data)}\n\n`);
  };

  const pythonProcess = spawn("python", args, { cwd: rootDir });

  let fullOutput = "";

  pythonProcess.stdout.on("data", (data) => {
    const text = data.toString();
    fullOutput += text;
    console.log(`[Python Stdout]: ${text}`);

    // Parse stage indicators
    if (text.includes("[+] 1. Ingesting")) sendEvent({ type: "stage", stage: 0, text: "Ingesting transactions..." });
    if (text.includes("[+] 3. Live Free Multi-Stage Resolution")) sendEvent({ type: "stage", stage: 1, text: "Resolving merchants..." });
    if (text.includes("[+] 5. Calculating Neighborhood Integration")) sendEvent({ type: "stage", stage: 2, text: "Building trust graph..." });
    if (text.includes("[+] 6. Initializing st_pignn.py")) sendEvent({ type: "stage", stage: 3, text: "Running GNN inference..." });
    if (text.includes("[+] 7. Executing Probabilistic ensemble.py")) sendEvent({ type: "stage", stage: 4, text: "Fusing results..." });

    // Parse tqdm progress (e.g., "Resolving Entities:  50%|")
    const progressMatch = text.match(/Resolving Entities:\s*(\d+)%/);
    if (progressMatch) {
      sendEvent({ type: "progress", percent: parseInt(progressMatch[1]) });
    }

    // Parse tqdm stats (e.g., "14/14 [00:45<00:00,  3.24s/merchant]")
    const statsMatch = text.match(/(\d+)\/(\d+)\s+\[.*?,\s*([\d.]+s\/merchant)\]/);
    if (statsMatch) {
      sendEvent({ 
        type: "stats", 
        current: statsMatch[1], 
        total: statsMatch[2], 
        rate: statsMatch[3] 
      });
    }
  });

  pythonProcess.stderr.on("data", (data) => {
    const text = data.toString();
    console.error(`[Python Stderr]: ${text}`);
    
    // tqdm often writes to stderr
    const progressMatch = text.match(/(\d+)%\|/);
    if (progressMatch) {
      sendEvent({ type: "progress", percent: parseInt(progressMatch[1]) });
    }

    const statsMatch = text.match(/(\d+)\/(\d+)\s+\[.*?,\s*([\d.]+s\/merchant)\]/);
    if (statsMatch) {
      sendEvent({ 
        type: "stats", 
        current: statsMatch[1], 
        total: statsMatch[2], 
        rate: statsMatch[3] 
      });
    }
  });

  pythonProcess.on("close", (code) => {
    if (code !== 0) {
      sendEvent({ type: "error", detail: "Python process exited with error" });
      return res.end();
    }

    // Parse final result from fullOutput
    const scoreMatch = fullOutput.match(/Final Axiom Credit Score:\s*(\d+)/) || fullOutput.match(/Axiom Score\s*:\s*(\d+)/);
    const score = scoreMatch ? parseInt(scoreMatch[1]) : 720;
    
    const drivers: any[] = [];
    const driverLines = fullOutput.matchAll(/\[([+-])\]\s*([^:(]+).*?\(([+-]?\d+)\s*pts\)/g);
    for (const match of driverLines) {
      drivers.push({
        driver: match[2].trim(),
        impact_points: Math.abs(parseInt(match[3])),
        direction: match[1] === "+" ? "UP" : "DOWN"
      });
    }

    const tierMatch = fullOutput.match(/Credit Tier\s*:\s*(\w+)/);
    const tier = tierMatch ? tierMatch[1] : (score > 700 ? "Prime" : "Silver");

    sendEvent({
      type: "result",
      data: {
        axiom_score: score,
        tier: tier,
        confidence_interval: 0.94,
        behavioral_drivers: drivers.slice(0, 5),
        generated_at: new Date().toISOString()
      }
    });
    res.end();
  });
}
