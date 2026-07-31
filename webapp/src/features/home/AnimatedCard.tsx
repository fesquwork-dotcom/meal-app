import type { FC, ReactNode } from 'react';
import { motion } from 'framer-motion';

export interface AnimatedCardProps {
  children: ReactNode;
  delay?: number;
}

export const AnimatedCard: FC<AnimatedCardProps> = ({ children, delay = 0 }) => (
  <motion.div
    initial={{ opacity: 0, y: 16 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.35, delay, ease: 'easeOut' }}
  >
    {children}
  </motion.div>
);
