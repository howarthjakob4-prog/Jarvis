# JARVIS V1 — Phone Line & Remote Approval Setup

This is part of the JARVIS V1 setup patch.

## Setup screen requirements

During first-run setup, JARVIS should include a **Phone & Remote Approvals** screen with:

- Owner phone number field
- Verification code step
- Enable approval calls toggle
- Enable approval text messages toggle
- Notify phone when laptop lid is closed
- Call the owner if a notification is not answered
- Test My Phone button
- Clear success/failure status before setup can mark the phone line as verified

## Approval behavior

When JARVIS reaches an action that requires owner approval:

1. Create a pending approval request.
2. Send the request to the verified owner phone.
3. If the laptop lid is closed, prioritize the phone notification path.
4. If enabled and the notification is not answered, place an approval call.
5. Accept only a verified approval or denial response.
6. Resume the pending action only after approval.
7. Log the event without writing the full phone number, verification code, provider secret, or call credentials to the log.

## Phone approval log

Default log path:

`data/logs/phone_approvals.log`

Recommended log events:

- phone_setup_started
- verification_requested
- phone_verified
- phone_verification_failed
- approval_requested
- notification_sent
- approval_call_requested
- approval_approved
- approval_denied
- approval_timed_out
- phone_service_error

Phone numbers in logs should be masked, for example `***-***-1234`.

## Configuration

The default configuration is stored under `phone_approvals` in `config/default.yaml`.

The phone service provider and JARVIS phone number remain blank until the calling/text service is connected. No personal phone number or provider credential is committed to GitHub.
