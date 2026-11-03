import { zodResolver } from "@hookform/resolvers/zod";
import { Activity, Loader2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { requestPasswordReset, resetPassword } from "@/api/auth";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const requestSchema = z.object({ email: z.email("Enter a valid email") });
const resetSchema = z
  .object({ password: z.string().min(8, "Use at least 8 characters"), confirm: z.string() })
  .refine((v) => v.password === v.confirm, { message: "Passwords don't match", path: ["confirm"] });

function FieldError({ message }: { message?: string }) {
  return message ? <p className="text-xs text-destructive">{message}</p> : null;
}

/** /forgot-password asks for an e-mail; the e-mailed link opens /reset-password?token=... */
export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const navigate = useNavigate();
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const requestForm = useForm<z.infer<typeof requestSchema>>({ resolver: zodResolver(requestSchema) });
  const resetForm = useForm<z.infer<typeof resetSchema>>({ resolver: zodResolver(resetSchema) });

  const onRequest = requestForm.handleSubmit(async ({ email }) => {
    setMessage(null);
    try {
      setMessage({ ok: true, text: await requestPasswordReset(email) });
    } catch (err) {
      setMessage({ ok: false, text: err instanceof Error ? err.message : "Could not send the reset e-mail" });
    }
  });

  const onReset = resetForm.handleSubmit(async ({ password }) => {
    if (!token) return;
    setMessage(null);
    try {
      await resetPassword(token, password);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setMessage({ ok: false, text: err instanceof Error ? err.message : "Could not reset the password" });
    }
  });

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-gradient-to-br from-primary/5 via-background to-background px-4">
      <div className="flex items-center gap-2 text-2xl font-semibold">
        <Activity className="size-6 text-primary" /> InvestAd
      </div>
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>{token ? "Choose a new password" : "Reset your password"}</CardTitle>
          <CardDescription>
            {token ? "This link works once and expires 30 minutes after it was sent." : "We'll e-mail you a link to choose a new password."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {message && (
            <Alert variant={message.ok ? "default" : "destructive"}>
              <AlertDescription>{message.text}</AlertDescription>
            </Alert>
          )}
          {token ? (
            <form onSubmit={onReset} className="space-y-4" noValidate>
              <div className="space-y-1.5">
                <Label htmlFor="reset-password">New password</Label>
                <Input id="reset-password" type="password" autoComplete="new-password" {...resetForm.register("password")} />
                <FieldError message={resetForm.formState.errors.password?.message} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="reset-confirm">Confirm new password</Label>
                <Input id="reset-confirm" type="password" autoComplete="new-password" {...resetForm.register("confirm")} />
                <FieldError message={resetForm.formState.errors.confirm?.message} />
              </div>
              <Button className="w-full" disabled={resetForm.formState.isSubmitting}>
                {resetForm.formState.isSubmitting && <Loader2 className="animate-spin" />} Set password and sign in
              </Button>
            </form>
          ) : (
            <form onSubmit={onRequest} className="space-y-4" noValidate>
              <div className="space-y-1.5">
                <Label htmlFor="reset-email">Email</Label>
                <Input id="reset-email" type="email" autoComplete="email" {...requestForm.register("email")} />
                <FieldError message={requestForm.formState.errors.email?.message} />
              </div>
              <Button className="w-full" disabled={requestForm.formState.isSubmitting}>
                {requestForm.formState.isSubmitting && <Loader2 className="animate-spin" />} Send reset link
              </Button>
            </form>
          )}
          <p className="text-center text-sm">
            <Link to="/login" className="text-primary hover:underline">
              Back to log in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
