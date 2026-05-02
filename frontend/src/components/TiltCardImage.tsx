import { PointerEvent, useState } from "react";
import Image from "next/image";
import { Box } from "@chakra-ui/react";
import { motion } from "framer-motion";

type TiltCardImageProps = {
  src: string;
  alt: string;
  width?: number;
};

const MotionBox = motion(Box);

export function TiltCardImage({ src, alt, width = 320 }: TiltCardImageProps) {
  const [rotation, setRotation] = useState({ rotateX: 0, rotateY: 0, scale: 1 });

  function updateRotation(clientX: number, clientY: number, element: HTMLDivElement) {
    const rect = element.getBoundingClientRect();
    const x = clientX - rect.left;
    const y = clientY - rect.top;

    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    const rotateY = ((x - centerX) / centerX) * 14;
    const rotateX = -((y - centerY) / centerY) * 14;

    setRotation({
      rotateX,
      rotateY,
      scale: 1.03,
    });
  }

  function handlePointerMove(event: PointerEvent<HTMLDivElement>) {
    updateRotation(event.clientX, event.clientY, event.currentTarget);
  }

  function resetRotation() {
    setRotation({ rotateX: 0, rotateY: 0, scale: 1 });
  }

  return (
    <Box
      position="relative"
      display="flex"
      alignItems="center"
      justifyContent="center"
      cursor="pointer"
      w="100%"
      style={{ perspective: "1000px", touchAction: "none" }}
    >
      <MotionBox
        onPointerMove={handlePointerMove}
        onPointerLeave={resetRotation}
        onPointerUp={resetRotation}
        onPointerCancel={resetRotation}
        animate={rotation}
        transition={{ type: "spring", stiffness: 150, damping: 16, mass: 0.9 }}
        style={{ transformStyle: "preserve-3d", width: `${width}px`, maxWidth: "100%", touchAction: "none" }}
        borderRadius="28px"
        overflow="hidden"
        boxShadow="0 20px 38px rgba(0, 0, 0, 0.36), 0 0 24px rgba(246, 196, 90, 0.08)"
      >
        <Box
          position="absolute"
          inset="0"
          zIndex={2}
          pointerEvents="none"
          bg="linear-gradient(115deg, rgba(255,255,255,0.16) 0%, rgba(255,255,255,0.04) 24%, rgba(255,255,255,0) 52%)"
          transform="translateZ(26px)"
        />
        <Box
          position="absolute"
          inset="auto 8% 8% auto"
          w="40%"
          h="28%"
          borderRadius="999px"
          zIndex={2}
          pointerEvents="none"
          bg="radial-gradient(circle, rgba(246,196,90,0.14) 0%, rgba(246,196,90,0) 72%)"
          transform="translateZ(18px)"
        />
        <Image
          src={src}
          alt={alt}
          width={1600}
          height={1200}
          priority
          style={{ width: "100%", height: "auto", display: "block" }}
        />
      </MotionBox>
    </Box>
  );
}
