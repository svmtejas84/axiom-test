import type { NextApiRequest, NextApiResponse } from "next";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function forwardJsonRequest(
  req: NextApiRequest,
  res: NextApiResponse,
  path: string
) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ message: "Method not allowed" });
  }

  try {
    const response = await fetch(`${BACKEND_URL}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(req.body),
    });

    const text = await response.text();
    const data = text ? JSON.parse(text) : {};

    return res.status(response.status).json(data);
  } catch (error) {
    return res.status(502).json({
      message: "Backend connection failed",
      detail: error instanceof Error ? error.message : "Unknown error",
    });
  }
}
