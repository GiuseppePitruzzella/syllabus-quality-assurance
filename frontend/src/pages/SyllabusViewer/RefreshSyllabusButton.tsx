import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Dialog } from "@base-ui/react/dialog";
import { Loader2, RefreshCw, X } from "lucide-react";
import { toast } from "sonner";
import { scrapeSyllabusDetail } from "@/lib/api";
import { Button } from "@/components/ui/button";

/**
 * Re-download (refresh) of a single syllabus from the SmartEdu portal.
 *
 * Addresses the "updated syllabus" case: once a teacher has corrected the
 * syllabus on the portal, the reviewer can force a fresh fetch of its content
 * here, instead of relying on the auto-scrape that only fires when the local
 * content is still empty. The evaluation history already shown in the viewer
 * then lets the reviewer compare a new evaluation against the previous one.
 *
 * Re-downloading overwrites the locally stored content; past evaluations are
 * preserved and remain consultable in the history list.
 */
export function RefreshSyllabusButton({ seuid }: { seuid: string }) {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => scrapeSyllabusDetail(seuid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["syllabus", seuid] });
      toast.success("Syllabus aggiornato", {
        description: "Contenuto riscaricato dal portale.",
      });
      setOpen(false);
    },
    onError: (error: unknown) => {
      toast.error("Aggiornamento fallito", {
        description:
          error instanceof Error
            ? error.message
            : "Errore durante il download del syllabus.",
      });
    },
  });

  return (
    <>
      <Button
        variant="outline"
        size="lg"
        onClick={() => setOpen(true)}
        className="rounded-none shadow-none"
      >
        <RefreshCw className="h-4 w-4" aria-hidden />
        Aggiorna
      </Button>
      <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Portal>
          <Dialog.Backdrop className="fixed inset-0 z-50 bg-slate-950/40 backdrop-blur-sm data-[ending-style]:animate-out data-[ending-style]:fade-out-0 data-[starting-style]:animate-in data-[starting-style]:fade-in-0" />
          <Dialog.Popup className="fixed left-1/2 top-1/2 z-50 flex w-[min(480px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-lg border bg-card shadow-lg data-[ending-style]:animate-out data-[ending-style]:fade-out-0 data-[ending-style]:zoom-out-95 data-[starting-style]:animate-in data-[starting-style]:fade-in-0 data-[starting-style]:zoom-in-95">
            <div className="flex items-start justify-between gap-4 border-b p-5">
              <div className="min-w-0 space-y-0.5">
                <Dialog.Title className="text-base font-semibold tracking-normal">
                  Aggiorna syllabus
                </Dialog.Title>
                <Dialog.Description className="text-xs text-muted-foreground">
                  Riscarica il contenuto aggiornato dal portale. Il contenuto
                  locale viene sovrascritto; le valutazioni precedenti restano
                  consultabili nello storico.
                </Dialog.Description>
              </div>
              <Dialog.Close
                className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                aria-label="Chiudi"
              >
                <X className="h-4 w-4" aria-hidden />
              </Dialog.Close>
            </div>
            <div className="flex justify-end gap-2 border-t p-4">
              <Dialog.Close
                className="inline-flex h-9 items-center px-3 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
                disabled={mutation.isPending}
              >
                Annulla
              </Dialog.Close>
              <Button
                onClick={() => mutation.mutate()}
                disabled={mutation.isPending}
                className="rounded-none bg-slate-950 text-white shadow-none hover:bg-slate-800"
              >
                {mutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                ) : (
                  <RefreshCw className="h-4 w-4" aria-hidden />
                )}
                Aggiorna
              </Button>
            </div>
          </Dialog.Popup>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
