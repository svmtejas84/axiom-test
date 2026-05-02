import type { NextApiRequest, NextApiResponse } from "next";
import { exec } from "child_process";
import path from "path";
import fs from "fs";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "POST") {
    return res.status(405).json({ detail: "Method not allowed" });
  }

  const { upi_id, parent_vpa, landlord_vpa, user_id } = req.body;

  // 1. Map VPA to Mock CSV (Mirroring main_execution.py logic)
  let mockPath = "";
  if (upi_id === "tejas26@okaxis") mockPath = "examples/high_trust_neighborhood.csv";
  else if (upi_id === "rahul@upi") mockPath = "examples/medium_trust_neighborhood.csv";
  else if (upi_id === "john21@upi") mockPath = "examples/low_trust_neighborhood.csv";
  else {
    const handle = upi_id?.split("@")[0] || "test_data1";
    mockPath = `examples/${handle}.csv`;
  }

  // Fallback if not found
  const fullMockPath = path.join(process.cwd(), "..", mockPath);
  const finalPath = fs.existsSync(fullMockPath) ? mockPath : "test_data1.csv";

  // 2. Build command for run_axiom_stateless.py
  // Note: We assume we are in <root>/frontend/src/pages/api/backend
  // Root is 4 levels up
  const rootDir = path.join(process.cwd(), "..");
  const scriptPath = "axiom_merchant_sandbox/run_axiom_stateless.py";
  
  let command = `python ${scriptPath} ${finalPath}`;
  if (req.body.student_verified || upi_id) command += " --student-verified";
  if (req.body.rent_verified || landlord_vpa) command += " --rent-verified";
  if (parent_vpa) command += ` --parent-vpa ${parent_vpa}`;
  if (landlord_vpa) command += ` --landlord-vpa ${landlord_vpa}`;

  console.log(`Executing integrated pipeline: ${command}`);

  exec(command, { cwd: rootDir }, (error, stdout, stderr) => {
    if (error) {
      console.error(`Exec error: ${error}`);
      return res.status(500).json({ detail: stderr || error.message });
    }

    // 3. Parse Output (SHAP Waterfall and Score)
    // Example line: "Final Axiom Credit Score: 745"
    const scoreMatch = stdout.match(/Final Axiom Credit Score:\s*(\d+)/);
    const score = scoreMatch ? parseInt(scoreMatch[1]) : 750;

    // Extract Waterfall drivers
    // Format: "    [+] Driver Name: +25"
    const drivers: any[] = [];
    const driverLines = stdout.matchAll(/\[([+-])\]\s*([^:]+):\s*([+-]?\d+)/g);
    for (const match of driverLines) {
      drivers.push({
        driver: match[2].trim(),
        impact_points: Math.abs(parseInt(match[3])),
        direction: match[1] === "+" ? "UP" : "DOWN"
      });
    }

    // Extract Tier
    const tier = score > 700 ? "Prime" : score > 500 ? "Silver" : "Bronze";

    return res.status(200).json({
      axiom_score: score,
      tier: tier,
      confidence_interval: 0.94,
      behavioral_drivers: drivers.slice(0, 5),
      generated_at: new Date().toISOString()
    });
  });
}
