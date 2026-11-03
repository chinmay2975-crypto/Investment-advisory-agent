import { zodResolver } from "@hookform/resolvers/zod";
import { Activity, Loader2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import { useAuth } from "@/auth/AuthContext";
import { GENERAL_NOTICE } from "@/components/Disclaimer";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const loginSchema = z.object({
  email: z.email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});
const signupSchema = loginSchema.extend({
  password: z.string().min(8, "Use at least 8 characters"),
  fullName: z.string().max(100).optional(),
});

type LoginValues = z.infer<typeof loginSchema>;
type SignupValues = z.infer<typeof signupSchema>;

function FieldError({ message }: { message?: string }) {
  return message ? <p className="text-xs text-destructive">{message}</p> : null;
}

export default function LoginPage() {
  const { login, signup } = useAuth();
  const navigate = useNavigate();
  const [serverError, setServerError] = useState<string | null>(null);

  const loginForm = useForm<LoginValues>({ resolver: zodResolver(loginSchema) });
  const signupForm = useForm<SignupValues>({ resolver: zodResolver(signupSchema) });

  const onLogin = loginForm.handleSubmit(async (values) => {
    setServerError(null);
    try {
      await login(values.email, values.password);
      navigate("/dashboard");
    } catch (err) {
      setServerError(err instanceof Error ? err.message : "Login failed");
    }
  });

  const onSignup = signupForm.handleSubmit(async (values) => {
    setServerError(null);
    try {
      await signup(values.email, values.password, values.fullName);
      navigate("/onboarding");
    } catch (err) {
      setServerError(err instanceof Error ? err.message : "Sign-up failed");
    }
  });

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-gradient-to-br from-primary/5 via-background to-background px-4">
      <div className="flex items-center gap-2 text-2xl font-semibold">
        <Activity className="size-6 text-primary" /> InvestAd
      </div>
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Welcome</CardTitle>
          <CardDescription>Country-aware portfolio insights for India, the US and the UK.</CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="login" onValueChange={() => setServerError(null)}>
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="login">Log in</TabsTrigger>
              <TabsTrigger value="signup">Sign up</TabsTrigger>
            </TabsList>

            {serverError && (
              <Alert variant="destructive" className="mt-4">
                <AlertDescription>{serverError}</AlertDescription>
              </Alert>
            )}

            <TabsContent value="login">
              <form onSubmit={onLogin} className="space-y-4" noValidate>
                <div className="space-y-1.5">
                  <Label htmlFor="login-email">Email</Label>
                  <Input id="login-email" type="email" autoComplete="email" {...loginForm.register("email")} />
                  <FieldError message={loginForm.formState.errors.email?.message} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="login-password">Password</Label>
                  <Input id="login-password" type="password" autoComplete="current-password" {...loginForm.register("password")} />
                  <FieldError message={loginForm.formState.errors.password?.message} />
                </div>
                <Button className="w-full" disabled={loginForm.formState.isSubmitting}>
                  {loginForm.formState.isSubmitting && <Loader2 className="animate-spin" />} Log in
                </Button>
              </form>
            </TabsContent>

            <TabsContent value="signup">
              <form onSubmit={onSignup} className="space-y-4" noValidate>
                <div className="space-y-1.5">
                  <Label htmlFor="signup-name">Full name (optional)</Label>
                  <Input id="signup-name" autoComplete="name" {...signupForm.register("fullName")} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="signup-email">Email</Label>
                  <Input id="signup-email" type="email" autoComplete="email" {...signupForm.register("email")} />
                  <FieldError message={signupForm.formState.errors.email?.message} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="signup-password">Password</Label>
                  <Input id="signup-password" type="password" autoComplete="new-password" {...signupForm.register("password")} />
                  <FieldError message={signupForm.formState.errors.password?.message} />
                </div>
                <Button className="w-full" disabled={signupForm.formState.isSubmitting}>
                  {signupForm.formState.isSubmitting && <Loader2 className="animate-spin" />} Create account
                </Button>
              </form>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
      <p className="max-w-md text-center text-xs text-muted-foreground">{GENERAL_NOTICE}</p>
    </div>
  );
}
