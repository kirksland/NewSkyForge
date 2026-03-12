
// ------------------------------------------------------
// rotate around SOURCE vertex (src) once
// ------------------------------------------------------
int rot_src(int h)
{
    int hp = hedge_prev(0, h);
    if (!hedge_isvalid(0, hp)) return -1;

    int hr = hedge_nextequiv(0, hp);
    if (!hedge_isvalid(0, hr)) return -1;

    return hr;
}


// ------------------------------------------------------
// helper: mark a stop point + reason attribute
// reason codes (example):
//   1 = boundary/unshared encountered (no opposite half-edge)
//   2 = valence != 4 encountered (ambiguous for quad loop)
//   3 = degenerate / invalid next / backtrack
// ------------------------------------------------------
void mark_stop(int pt; int reason; string g_unshared; string g_non4; string g_deg)
{
    if (reason == 1) setpointgroup(0, g_unshared, pt, 1);
    else if (reason == 2) setpointgroup(0, g_non4, pt, 1);
    else setpointgroup(0, g_deg, pt, 1);

    // per-point debug attrib (keeps the last reason if hit multiple times)
    setpointattrib(0, "stop_reason", pt, reason, "set");
}

// ------------------------------------------------------
// walk edge-loop in one direction, starting from prev->cur
// Adds edges to outgrp.
// Marks stop points when it cannot continue.
// ------------------------------------------------------
int walk_loop(int prev; int cur; string outgrp; int maxit;
              string g_unshared; string g_non4; string g_deg;
              int mark_cand_boundary)
{
    int it = 0;

    for (it = 0; it < maxit; it++)
    {
        // incoming half-edge prev->cur
        int hin = pointhedge(0, prev, cur);
        if (!hedge_isvalid(0, hin))
        {
            mark_stop(cur, 3, g_unshared, g_non4, g_deg);
            break;
        }

        // if no opposite half-edge => boundary/unshared
        int hout0 = hedge_nextequiv(0, hin); // cur->prev
        if (!hedge_isvalid(0, hout0))
        {
            mark_stop(cur, 1, g_unshared, g_non4, g_deg);
            break;
        }

        // edge-loop selection is unambiguous on regular quad valence-4
        int nb[] = neighbours(0, cur);
        if (len(nb) != 4)
        {
            mark_stop(cur, 2, g_unshared, g_non4, g_deg);
            break;
        }

        // opposite edge around vertex = rotate twice (valence 4 => +2)
        int hout = rot_src(hout0);
        if (!hedge_isvalid(0, hout))
        {
            mark_stop(cur, 3, g_unshared, g_non4, g_deg);
            break;
        }

        hout = rot_src(hout);
        if (!hedge_isvalid(0, hout))
        {
            mark_stop(cur, 3, g_unshared, g_non4, g_deg);
            break;
        }

        int nxt = hedge_dstpoint(0, hout);
        if (nxt < 0 || nxt == prev)
        {
            mark_stop(cur, 3, g_unshared, g_non4, g_deg);
            break;
        }

        // Optional: detect if the candidate edge cur->nxt is itself boundary/unshared
        if (mark_cand_boundary)
        {
            int hcand = pointhedge(0, cur, nxt);
            if (hedge_isvalid(0, hcand))
            {
                int ht = hedge_nextequiv(0, hcand);
                if (!hedge_isvalid(0, ht))
                {
                    // we still add that last boundary edge, then mark stop and exit
                    setedgegroup(0, outgrp, cur, nxt, 1);
                    mark_stop(cur, 1, g_unshared, g_non4, g_deg);
                    break;
                }
            }
        }

        // add edge cur->nxt
        setedgegroup(0, outgrp, cur, nxt, 1);

        prev = cur;
        cur  = nxt;
    }

    return it;
}


// marche dans une direction de ring à partir d’un half-edge (dirigé)
int walk_rail(int hstart; string outgrp; int maxit)
{
    int hcur = hstart;
    int it = 0;

    while (it < maxit)
    {
        if (!hedge_isvalid(0, hcur)) break;

        int prim = hedge_prim(0, hcur);
        if (prim < 0) break;
        if (primvertexcount(0, prim) != 4) break; // ring défini quad-only

        // opposée dans le quad
        int hop = hedge_next(0, hedge_next(0, hcur));
        if (!hedge_isvalid(0, hop)) break;

        int a = hedge_srcpoint(0, hop);
        int b = hedge_dstpoint(0, hop);
        setedgegroup(0, outgrp, a, b, 1);

        // traverser vers la face adjacente à cette opposée
        int htwin = hedge_nextequiv(0, hop);
        if (!hedge_isvalid(0, htwin)) break;

        // éviter boucle débile
        if (htwin == hcur) break;

        hcur = htwin;
        it++;
    }
    return it;
}

void test1(string test)
{
    printf("test %s\n",test);
}