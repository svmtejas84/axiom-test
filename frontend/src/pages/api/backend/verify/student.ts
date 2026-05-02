import type { NextApiRequest, NextApiResponse } from "next";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  // Simulate student verification
  // Approved for institutional domains as per sheerid_service.py logic
  const { edu_email } = req.body;
  const domain = edu_email?.split("@")?.[1] || "";
  
  const institutionalSuffixes = [".edu", ".ac.in", ".edu.in", ".ac.uk", ".res.in", ".gov.in"];
  const isInstitutional = institutionalSuffixes.some(suffix => domain.endsWith(suffix));

  if (!isInstitutional) {
    return res.status(400).json({ 
      detail: `Email domain (@${domain}) is not recognized as a student institution. Please use an official .edu or .ac.in email.` 
    });
  }

  return res.status(200).json({
    verification_id: "mock_student_id",
    status: "verified",
    trust_boost_applied: true
  });
}
