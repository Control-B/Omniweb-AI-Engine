import { type ActionFunctionArgs, type LoaderFunctionArgs } from "@remix-run/node";
import { Form, useActionData, useLoaderData } from "@remix-run/react";
import { login } from "../shopify.server";

export async function loader({ request }: LoaderFunctionArgs) {
  const url = new URL(request.url);
  return { shop: url.searchParams.get("shop") || "" };
}

export async function action({ request }: ActionFunctionArgs) {
  const formData = await request.formData();
  const shop = String(formData.get("shop") || "").trim();
  if (!shop) return { error: "Please enter your store URL." };
  return login(request);
}

export default function AuthLogin() {
  const { shop } = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", fontFamily: "system-ui, sans-serif", background: "#f6f6f7" }}>
      <div style={{ background: "#fff", borderRadius: 12, padding: "2.5rem 2rem", boxShadow: "0 2px 16px rgba(0,0,0,.1)", width: 340 }}>
        <h1 style={{ marginTop: 0, fontSize: "1.25rem" }}>Install Omniweb</h1>
        <Form method="post">
          <label style={{ display: "block", marginBottom: ".4rem", fontSize: ".9rem", color: "#555" }}>
            Shopify store URL
          </label>
          <input
            name="shop"
            defaultValue={shop}
            placeholder="your-store.myshopify.com"
            required
            style={{ width: "100%", boxSizing: "border-box", padding: ".6rem .75rem", borderRadius: 8, border: "1px solid #ccc", fontSize: "1rem", marginBottom: ".75rem" }}
          />
          {"error" in (actionData || {}) && (
            <p style={{ color: "red", fontSize: ".85rem", margin: "0 0 .5rem" }}>{(actionData as { error: string }).error}</p>
          )}
          <button type="submit" style={{ width: "100%", padding: ".7rem", borderRadius: 8, background: "#008060", color: "#fff", border: "none", fontSize: "1rem", cursor: "pointer" }}>
            Install app
          </button>
        </Form>
      </div>
    </div>
  );
}
