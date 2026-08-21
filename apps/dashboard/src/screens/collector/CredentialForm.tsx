// DP-034 D1's write-only credential field. Two inputs (purpose, value), one
// write (`POST /sources/{id}/credentials`), and nothing that reads a value
// back — the screen shows only the derived ref name and whether it is
// configured, never the value itself.
//
// The backend route is Lane A's (controller ruling 2026-08-21: the domain API
// owns source routes) and is not served yet; this component's tests mock the
// write. `configuredPurposes` is likewise mocked from source detail until
// M2's domain API lands — batch 5d wires both for real.

import {
  Alert,
  Box,
  Button,
  Chip,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import type { FormEvent, JSX } from "react";
import { useState } from "react";

import { credentialRefName, isCredentialWriteFailure } from "../../api/client";
import { useCredentialWriteMutation } from "../../api/queries";

export interface CredentialFormProps {
  sourceId: string;
  /** Purposes this source already has a value configured for (mocked from source detail). */
  configuredPurposes: readonly string[];
}

export function CredentialForm({ sourceId, configuredPurposes }: CredentialFormProps): JSX.Element {
  const [purpose, setPurpose] = useState("");
  const [value, setValue] = useState("");
  const [justConfigured, setJustConfigured] = useState<string | null>(null);
  const mutation = useCredentialWriteMutation();

  const trimmedPurpose = purpose.trim();
  const ref = trimmedPurpose === "" ? null : credentialRefName(sourceId, trimmedPurpose);
  const configured =
    trimmedPurpose !== "" &&
    (configuredPurposes.includes(trimmedPurpose) || justConfigured === trimmedPurpose);

  function onSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (trimmedPurpose === "" || value === "") {
      return;
    }
    const purposeAtSubmit = trimmedPurpose;
    const valueAtSubmit = value;
    // Cleared before the request is even sent, success or failure alike: the
    // value must not linger in this component's own state beyond firing it.
    setValue("");
    mutation.mutate(
      { sourceId, purpose: purposeAtSubmit, value: valueAtSubmit },
      { onSuccess: () => setJustConfigured(purposeAtSubmit) },
    );
  }

  const failure = mutation.error;

  return (
    <Box component="form" onSubmit={onSubmit} sx={{ mt: 1 }}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Write-only: a submitted value is never read back or displayed. Only its ref name and
        whether it is configured are shown.
      </Typography>
      <Stack direction="row" spacing={1} sx={{ mb: 1 }} flexWrap="wrap" useFlexGap alignItems="center">
        <TextField
          size="small"
          label="purpose"
          value={purpose}
          onChange={(event) => setPurpose(event.target.value)}
        />
        <TextField
          size="small"
          type="password"
          label="value"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          autoComplete="off"
        />
        <Button
          type="submit"
          variant="contained"
          disabled={mutation.isPending || trimmedPurpose === "" || value === ""}
        >
          Save
        </Button>
      </Stack>
      {ref === null ? null : (
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
          <Typography variant="body2">
            ref: <code>{ref}</code>
          </Typography>
          <Chip
            size="small"
            label={configured ? "configured" : "not configured"}
            color={configured ? "success" : "default"}
          />
        </Stack>
      )}
      {mutation.isError ? (
        <Alert severity="error">
          {isCredentialWriteFailure(failure)
            ? `${failure.error_class}: ${failure.error_summary}`
            : failure instanceof Error
              ? failure.message
              : "the write failed"}
        </Alert>
      ) : null}
    </Box>
  );
}
