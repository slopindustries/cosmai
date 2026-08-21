// DP-034 D1's write-only credential field. Two inputs (purpose, value), one
// write (`POST /sources/{id}/credentials`), and nothing that reads a value
// back — the screen shows only the derived ref name and whether *this
// session* wrote it, never the value itself and never a durable "configured"
// truth from the server.
//
// Real as of batch 5-final (`apps/domain/api.py`'s `write_source_credential`,
// merged from `dev`). **Mismatch found and fixed reconciling against the
// real route:** batch 5b/5c's version took a `configuredPurposes` prop and
// showed "configured"/"not configured" against it, implying a queryable
// server-known status. DP-034 D1's own text is explicit that the route is
// write-only and never reads a value back — there is no `GET` anywhere that
// reports whether a purpose is configured, so `configuredPurposes` was
// mocking information the real system cannot provide, not standing in for a
// route that just hadn't landed yet. Removed; the badge now reads "written
// this session" (this component's own `justConfigured` state, already
// present) or "not written this session" — never a claim about server state
// this component cannot see.

import { Alert, Box, Button, Chip, Stack, TextField, Typography } from "@mui/material";
import type { FormEvent, JSX } from "react";
import { useState } from "react";

import { credentialRefName, isCredentialWriteFailure } from "../../api/client";
import { useCredentialWriteMutation } from "../../api/queries";

export interface CredentialFormProps {
  sourceId: string;
}

export function CredentialForm({ sourceId }: CredentialFormProps): JSX.Element {
  const [purpose, setPurpose] = useState("");
  const [value, setValue] = useState("");
  const [justConfigured, setJustConfigured] = useState<string | null>(null);
  const mutation = useCredentialWriteMutation();

  const trimmedPurpose = purpose.trim();
  const ref = trimmedPurpose === "" ? null : credentialRefName(sourceId, trimmedPurpose);
  const writtenThisSession = trimmedPurpose !== "" && justConfigured === trimmedPurpose;

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
        Write-only: a submitted value is never read back or displayed, and the platform exposes no
        way to ask afterward whether a purpose is configured — only whether this screen wrote one
        this session.
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
            label={writtenThisSession ? "written this session" : "not written this session"}
            color={writtenThisSession ? "success" : "default"}
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
