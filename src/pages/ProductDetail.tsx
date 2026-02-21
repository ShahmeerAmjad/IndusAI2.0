import { useQuery } from "@tanstack/react-query";
import { api, Product } from "@/lib/api";
import { useParams, useNavigate } from "react-router-dom";
import { formatCurrency, cn } from "@/lib/utils";

export default function ProductDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: product, isLoading, isError, error } = useQuery({
    queryKey: ["product", id],
    queryFn: () => api.getProduct(id!),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-industrial-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-neutral-500 font-inter text-sm">Loading product details...</p>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 max-w-md text-center">
          <h3 className="text-red-800 font-semibold text-lg mb-2">Failed to load product</h3>
          <p className="text-red-600 text-sm">
            {error instanceof Error ? error.message : "An unexpected error occurred."}
          </p>
          <button
            onClick={() => navigate(-1)}
            className="mt-4 px-4 py-2 text-sm font-medium text-industrial-800 border border-industrial-300 rounded-lg hover:bg-industrial-50 transition-colors"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  if (!product) return null;

  const infoFields: Array<{ label: string; value: React.ReactNode }> = [
    { label: "Category", value: product.category },
    { label: "Subcategory", value: product.subcategory },
    { label: "Unit of Measure", value: product.uom },
    { label: "Min Order Qty", value: product.min_order_qty.toLocaleString() },
    {
      label: "Lead Time",
      value: `${product.lead_time_days} ${product.lead_time_days === 1 ? "day" : "days"}`,
    },
    {
      label: "Hazmat",
      value: product.hazmat ? (
        <span className="inline-block bg-red-100 text-red-700 text-xs font-semibold px-2 py-0.5 rounded">
          Yes
        </span>
      ) : (
        <span className="inline-block bg-green-100 text-green-700 text-xs font-semibold px-2 py-0.5 rounded">
          No
        </span>
      ),
    },
    { label: "Country of Origin", value: product.country_of_origin },
  ];

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Back Button */}
      <button
        onClick={() => navigate(-1)}
        className="inline-flex items-center gap-1.5 text-sm text-neutral-600 hover:text-industrial-800 transition-colors group"
      >
        <svg
          className="h-4 w-4 group-hover:-translate-x-0.5 transition-transform"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Back to Products
      </button>

      {/* Product Header */}
      <div className="bg-white border border-neutral-200 rounded-lg p-6">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
          <div>
            <h1 className="text-2xl font-montserrat font-bold text-neutral-900">
              {product.name}
            </h1>
            <p className="text-neutral-500 text-sm mt-1">{product.manufacturer}</p>
          </div>
          <span className="inline-block self-start bg-industrial-100 text-industrial-800 text-sm font-semibold px-3 py-1.5 rounded-md font-mono">
            {product.sku}
          </span>
        </div>

        {/* MPN */}
        {product.manufacturer_part_number && (
          <p className="text-xs text-neutral-400 mt-2">
            MPN: <span className="font-mono text-neutral-500">{product.manufacturer_part_number}</span>
          </p>
        )}
      </div>

      {/* Description */}
      {product.description && (
        <div className="bg-white border border-neutral-200 rounded-lg p-6">
          <h2 className="text-sm font-semibold text-neutral-700 uppercase tracking-wider mb-3">
            Description
          </h2>
          <p className="text-neutral-600 text-sm leading-relaxed">{product.description}</p>
        </div>
      )}

      {/* Info Grid */}
      <div className="bg-white border border-neutral-200 rounded-lg p-6">
        <h2 className="text-sm font-semibold text-neutral-700 uppercase tracking-wider mb-4">
          Product Information
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-4">
          {infoFields.map((field) => (
            <div key={field.label} className="flex flex-col">
              <dt className="text-xs font-medium text-neutral-400 uppercase tracking-wide">
                {field.label}
              </dt>
              <dd className="mt-1 text-sm text-neutral-900 font-medium">{field.value}</dd>
            </div>
          ))}
        </div>
      </div>

      {/* Specifications Table */}
      {product.specs && product.specs.length > 0 && (
        <div className="bg-white border border-neutral-200 rounded-lg p-6">
          <h2 className="text-sm font-semibold text-neutral-700 uppercase tracking-wider mb-4">
            Specifications
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-200">
                  <th className="text-left py-2.5 px-3 text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                    Specification
                  </th>
                  <th className="text-left py-2.5 px-3 text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                    Value
                  </th>
                  <th className="text-left py-2.5 px-3 text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                    Unit
                  </th>
                </tr>
              </thead>
              <tbody>
                {product.specs.map((spec, idx) => (
                  <tr
                    key={idx}
                    className={cn(
                      "border-b border-neutral-100",
                      idx % 2 === 0 ? "bg-neutral-50" : "bg-white"
                    )}
                  >
                    <td className="py-2.5 px-3 text-neutral-700 font-medium">{spec.name}</td>
                    <td className="py-2.5 px-3 text-neutral-600">{spec.value}</td>
                    <td className="py-2.5 px-3 text-neutral-500">{spec.unit ?? "--"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Cross References Table */}
      {product.cross_references && product.cross_references.length > 0 && (
        <div className="bg-white border border-neutral-200 rounded-lg p-6">
          <h2 className="text-sm font-semibold text-neutral-700 uppercase tracking-wider mb-4">
            Cross References
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-200">
                  <th className="text-left py-2.5 px-3 text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                    Type
                  </th>
                  <th className="text-left py-2.5 px-3 text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                    SKU
                  </th>
                  <th className="text-left py-2.5 px-3 text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                    Manufacturer
                  </th>
                </tr>
              </thead>
              <tbody>
                {product.cross_references.map((ref, idx) => (
                  <tr
                    key={idx}
                    className={cn(
                      "border-b border-neutral-100",
                      idx % 2 === 0 ? "bg-neutral-50" : "bg-white"
                    )}
                  >
                    <td className="py-2.5 px-3 text-neutral-700 font-medium capitalize">
                      {ref.cross_ref_type}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-neutral-600">{ref.cross_ref_sku}</td>
                    <td className="py-2.5 px-3 text-neutral-500">{ref.manufacturer ?? "--"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
