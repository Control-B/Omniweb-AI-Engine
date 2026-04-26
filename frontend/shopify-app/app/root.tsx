import type { HeadersFunction } from "@remix-run/node";
import {
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
} from "@remix-run/react";
import polarisStyles from "@shopify/polaris/build/esm/styles.css?url";
import { addDocumentResponseHeaders } from "./shopify.server";

export const links = () => [{ rel: "stylesheet", href: polarisStyles }];
export const headers: HeadersFunction = (headersArgs) => {
  return addDocumentResponseHeaders(headersArgs);
};

export default function App() {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width,initial-scale=1" />
        <Meta />
        <Links />
      </head>
      <body>
        <Outlet />
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}
