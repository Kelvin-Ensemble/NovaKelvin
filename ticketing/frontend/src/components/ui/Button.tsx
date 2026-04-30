import React from 'react';

interface ButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: 'default' | 'outline';
  className?: string;
  type?: 'button' | 'submit';
}

export const Button: React.FC<ButtonProps> = ({
  children,
  onClick,
  disabled,
  variant = "default",
  className = "",
  type = "button"
}) => {
  const baseStyles = "px-4 py-2 rounded-md font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed";
  const variants = {
    default: "bg-[#008888] text-white hover:bg-[#006666]",
    outline: "border-2 border-gray-300 text-gray-700 hover:bg-gray-50",
    outline_active: "border-2 border-[#008888] text-gray-700 hover:bg-[#008888] hover:text-white"
  };


  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${baseStyles} ${variants[variant]} ${className}`}
    >
      {children}
    </button>
  );
};