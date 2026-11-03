import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import { changePassword, deleteAccount } from "@/api/auth";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const passwordSchema = z
  .object({
    current: z.string().min(1, "Enter your current password"),
    next: z.string().min(8, "Use at least 8 characters"),
    confirm: z.string(),
  })
  .refine((v) => v.next === v.confirm, { message: "Passwords don't match", path: ["confirm"] })
  .refine((v) => v.next !== v.current, { message: "Choose a different password", path: ["next"] });

const deleteSchema = z.object({
  password: z.string().min(1, "Enter your password"),
  phrase: z.literal("DELETE", { message: "Type DELETE to confirm" }),
});

type PasswordValues = z.infer<typeof passwordSchema>;
type DeleteValues = z.infer<typeof deleteSchema>;

function FieldError({ message }: { message?: string }) {
  return message ? <p className="text-xs text-destructive">{message}</p> : null;
}

export default function AccountPage() {
  const navigate = useNavigate();
  const [passwordMessage, setPasswordMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const passwordForm = useForm<PasswordValues>({ resolver: zodResolver(passwordSchema) });
  const deleteForm = useForm<DeleteValues>({ resolver: zodResolver(deleteSchema) });

  const onChangePassword = passwordForm.handleSubmit(async (values) => {
    setPasswordMessage(null);
    try {
      await changePassword(values.current, values.next);
      passwordForm.reset();
      setPasswordMessage({ ok: true, text: "Password changed. Sessions on other devices have been signed out." });
    } catch (err) {
      setPasswordMessage({ ok: false, text: err instanceof Error ? err.message : "Could not change the password" });
    }
  });

  const onDelete = deleteForm.handleSubmit(async (values) => {
    setDeleteError(null);
    try {
      await deleteAccount(values.password);
      navigate("/login", { replace: true });
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Could not delete the account");
    }
  });

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Account</h1>
        <p className="text-sm text-muted-foreground">Change your password, or delete your account and its data.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Change password</CardTitle>
          <CardDescription>You stay signed in here; sessions on other devices end.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onChangePassword} className="space-y-4" noValidate>
            {passwordMessage && (
              <Alert variant={passwordMessage.ok ? "default" : "destructive"}>
                <AlertDescription>{passwordMessage.text}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="current-password">Current password</Label>
              <Input id="current-password" type="password" autoComplete="current-password" {...passwordForm.register("current")} />
              <FieldError message={passwordForm.formState.errors.current?.message} />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="new-password">New password</Label>
                <Input id="new-password" type="password" autoComplete="new-password" {...passwordForm.register("next")} />
                <FieldError message={passwordForm.formState.errors.next?.message} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="confirm-password">Confirm new password</Label>
                <Input id="confirm-password" type="password" autoComplete="new-password" {...passwordForm.register("confirm")} />
                <FieldError message={passwordForm.formState.errors.confirm?.message} />
              </div>
            </div>
            <Button disabled={passwordForm.formState.isSubmitting}>
              {passwordForm.formState.isSubmitting && <Loader2 className="animate-spin" />} Update password
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <ShieldAlert className="size-5" /> Delete account
          </CardTitle>
          <CardDescription>
            Permanently removes your profile, goals, holdings, suggestions and assessment history. This cannot be undone.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onDelete} className="space-y-4" noValidate>
            {deleteError && (
              <Alert variant="destructive">
                <AlertDescription>{deleteError}</AlertDescription>
              </Alert>
            )}
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="delete-password">Password</Label>
                <Input id="delete-password" type="password" autoComplete="current-password" {...deleteForm.register("password")} />
                <FieldError message={deleteForm.formState.errors.password?.message} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="delete-phrase">Type DELETE</Label>
                <Input id="delete-phrase" autoComplete="off" {...deleteForm.register("phrase")} />
                <FieldError message={deleteForm.formState.errors.phrase?.message} />
              </div>
            </div>
            <Button variant="destructive" disabled={deleteForm.formState.isSubmitting}>
              {deleteForm.formState.isSubmitting && <Loader2 className="animate-spin" />} Delete my account
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
