import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ArticlePage } from "@/components/ui/ArticlePage";
import { findPage, legalPages } from "@/lib/data/pages";

export function generateStaticParams() {
  return legalPages.map((p) => ({ slug: p.slug }));
}

export async function generateMetadata(props: PageProps<"/legal/[slug]">): Promise<Metadata> {
  const { slug } = await props.params;
  const page = findPage(legalPages, slug);
  if (!page) return {};
  return {
    title: page.title,
    description: page.intro,
    alternates: { canonical: `/legal/${slug}` },
  };
}

export default async function LegalPage(props: PageProps<"/legal/[slug]">) {
  const { slug } = await props.params;
  const page = findPage(legalPages, slug);
  if (!page) notFound();
  return <ArticlePage page={page} breadcrumb={{ label: "Légal", href: "/legal/mentions" }} />;
}
