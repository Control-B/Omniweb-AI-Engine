import { AppProvider } from "@shopify/shopify-app-remix/react";
import { NavMenu } from "@shopify/app-bridge-react";
import { Outlet, useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";

export async function loader({ request }: { request: Request }) {
  await authenticate.admin(request);
  return { apiKey: process.env.SHOPIFY_API_KEY || "" };
}

export default function EmbeddedAppLayout() {
  const { apiKey } = useLoaderData<typeof loader>();

  return (
    <AppProvider isEmbeddedApp apiKey={apiKey}>
      <NavMenu>
        <a href="/app" rel="home">Home</a>
        <a href="/app/agent">AI Agent</a>
        <a href="/app/knowledge">Knowledge</a>
        <a href="/app/billing">Billing</a>
        <a href="/app/analytics">Analytics</a>
      </NavMenu>
      <Outlet />
    </AppProvider>
  );
}
