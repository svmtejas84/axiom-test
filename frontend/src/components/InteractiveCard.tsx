import { PointerEvent, ReactNode, useState } from "react";
import { motion } from "framer-motion";

type InteractiveCardProps = {
  children: ReactNode;
  className?: string;
  style?: React.CSSProperties;
  tilt?: number;
  scale?: number;
};

const MotionDiv = motion.div;

export function InteractiveCard({
  children,
  className,
  style,
  tilt = 8,
  scale = 1.02,
}: InteractiveCardProps) {
  const [transform, setTransform] = useState({ rotateX: 0, rotateY: 0, scale: 1 });

  function updateTransform(clientX: number, clientY: number, element: HTMLDivElement) {
    const rect = element.getBoundingClientRect();
    const x = clientX - rect.left;
    const y = clientY - rect.top;
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;

    setTransform({
      rotateX: -((y - centerY) / centerY) * tilt,
      rotateY: ((x - centerX) / centerX) * tilt,
      scale,
    });
  }

  function handlePointerMove(event: PointerEvent<HTMLDivElement>) {
    updateTransform(event.clientX, event.clientY, event.currentTarget);
  }

  function resetTransform() {
    setTransform({ rotateX: 0, rotateY: 0, scale: 1 });
  }

  return (
    <MotionDiv
      className={className}
      style={{
        ...style,
        transformStyle: "preserve-3d",
        willChange: "transform",
        touchAction: "none",
      }}
      animate={transform}
      transition={{ type: "spring", stiffness: 160, damping: 18, mass: 0.85 }}
      onPointerMove={handlePointerMove}
      onPointerLeave={resetTransform}
      onPointerUp={resetTransform}
      onPointerCancel={resetTransform}
    >
      {children}
    </MotionDiv>
  );
}
