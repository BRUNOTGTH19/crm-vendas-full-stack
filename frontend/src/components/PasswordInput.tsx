import { useState, type InputHTMLAttributes } from "react";
import { IconEye, IconEyeOff } from "./icons.tsx";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "type">;

/**
 * Campo de senha com botão para revelar o texto digitado.
 *
 * Digitar às cegas é a causa mais comum de "senha incorreta" no celular; o
 * botão alterna entre os tipos `password` e `text` sem tirar o foco do campo.
 * Ele fica fora do fluxo do formulário (`type="button"`) e anuncia o estado
 * para leitores de tela.
 */
export function PasswordInput({ className = "field", ...props }: Props) {
  const [visible, setVisible] = useState(false);
  const label = visible ? "Ocultar senha" : "Mostrar senha";

  return (
    <div className="relative">
      <input
        {...props}
        type={visible ? "text" : "password"}
        className={`${className} pr-12`}
      />
      <button
        type="button"
        onClick={() => setVisible((current) => !current)}
        aria-label={label}
        aria-pressed={visible}
        title={label}
        className="absolute inset-y-0 right-0 flex w-12 items-center justify-center rounded-r-2xl text-ink/50 transition hover:text-ink dark:text-ink/60 dark:hover:text-ink"
      >
        {visible ? (
          <IconEyeOff className="h-5 w-5" />
        ) : (
          <IconEye className="h-5 w-5" />
        )}
      </button>
    </div>
  );
}
