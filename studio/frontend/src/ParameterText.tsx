import { useEffect, useRef, useState } from 'react';

type Format = 'lines' | 'thresholds' | 'colors';
interface Props {
  value: unknown[];
  format: Format;
  placeholder?: string;
  onValue: (value: unknown[]) => void;
  onError: (message: string) => void;
}

function display(value: unknown[], format: Format) {
  return format === 'colors' ? JSON.stringify(value) : value.join(format === 'lines' ? '\n' : ', ');
}

export function ParameterText({ value, format, placeholder, onValue, onError }: Props) {
  const signature = JSON.stringify(value);
  const published = useRef(signature);
  const [text, setText] = useState(() => display(value, format));
  const [error, setError] = useState('');
  useEffect(() => {
    if (signature !== published.current) {
      published.current = signature;
      setText(display(value, format));
      setError('');
      onError('');
    }
  }, [signature, format]);

  function change(raw: string) {
    setText(raw);
    try {
      let parsed: unknown[];
      if (format === 'lines') parsed = raw.split('\n').filter(line => line.length > 0);
      else if (format === 'thresholds') {
        const parts = raw.split(',').map(part => part.trim());
        if (parts.some(part => !part || !Number.isFinite(Number(part)) || Number(part) < 0 || Number(part) > 1)) {
          throw new Error('请输入 0–1 之间的阈值，使用逗号分隔');
        }
        parsed = parts.map(Number);
      } else {
        parsed = JSON.parse(raw);
        if (!Array.isArray(parsed) || !parsed.length || parsed.some(row => !Array.isArray(row) || row.length !== 3 || row.some(v => !Number.isInteger(v) || v < 0 || v > 255))) {
          throw new Error('使用三通道颜色数组，例如 [[0, 0, 0]]');
        }
      }
      published.current = JSON.stringify(parsed);
      setError(''); onError(''); onValue(parsed);
    } catch (cause) {
      const message = cause instanceof SyntaxError ? 'JSON 尚未完整，请继续编辑' : String(cause instanceof Error ? cause.message : cause);
      setError(message); onError(message);
    }
  }
  return <>{format === 'lines'
    ? <textarea rows={3} value={text} placeholder={placeholder} onChange={event => change(event.target.value)} />
    : <input value={text} aria-invalid={Boolean(error)} onChange={event => change(event.target.value)} />}
    {error && <small className="field-error" role="alert">{error}</small>}
  </>;
}
