// Renders a form from a manifest-shaped config schema. The field shape
// mirrors an add-on's `[[config.field]]` table in `addon.toml` — see
// `experiments/integrated-p0/addons/collector.naver.blog/addon.toml`:
// `name`, `type`, `required`, `label`, and an optional `help` string.
//
// P0-A never built a config-schema *renderer* (P0-A/P0-B sources had their
// config set by fixture, not by an operator screen), so there is nothing to
// copy-adapt here — this is new against the manifest field shape the addon.toml
// files already fix.

import { Box, Button, Stack, TextField } from "@mui/material";
import type { FormEvent, JSX } from "react";
import { useState } from "react";

export interface ConfigField {
  name: string;
  type: "string" | "integer";
  required: boolean;
  label: string;
  help?: string;
}

export interface ConfigSchemaFormProps {
  fields: readonly ConfigField[];
  onSubmit: (values: Record<string, string>) => void;
}

function validate(fields: readonly ConfigField[], values: Record<string, string>): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const field of fields) {
    const raw = (values[field.name] ?? "").trim();
    if (field.required && raw === "") {
      errors[field.name] = `${field.label} is required`;
      continue;
    }
    if (field.type === "integer" && raw !== "" && !/^-?\d+$/.test(raw)) {
      errors[field.name] = `${field.label} must be a whole number`;
    }
  }
  return errors;
}

export function ConfigSchemaForm({ fields, onSubmit }: ConfigSchemaFormProps): JSX.Element {
  const [values, setValues] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  function handleChange(name: string, next: string): void {
    setValues((previous) => ({ ...previous, [name]: next }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const nextErrors = validate(fields, values);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length === 0) {
      onSubmit(values);
    }
  }

  return (
    // `noValidate`: without it, a browser (jsdom included) runs its own HTML5
    // required-field constraint validation on submit and silently blocks the
    // `submit` event entirely when a required input is empty — before this
    // component's own `handleSubmit` ever runs. The MUI `helperText` error
    // below is this form's actual validation UI; native validation would
    // just shadow it with a browser tooltip and skip our error message.
    <Box component="form" onSubmit={handleSubmit} noValidate>
      <Stack spacing={2} alignItems="flex-start">
        {fields.map((field) => (
          <TextField
            key={field.name}
            label={field.label}
            required={field.required}
            type={field.type === "integer" ? "number" : "text"}
            value={values[field.name] ?? ""}
            onChange={(event) => handleChange(field.name, event.target.value)}
            error={Boolean(errors[field.name])}
            helperText={errors[field.name] ?? field.help}
            size="small"
            fullWidth
          />
        ))}
        <Button type="submit" variant="contained">
          Save config
        </Button>
      </Stack>
    </Box>
  );
}
