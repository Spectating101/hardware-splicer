// Hardware Splicer derived-surrogate testbench. NOT manufacturer evidence.
`timescale 1ns/1ps

module hs_w25q_readonly_oracle_tb;
    reg cs_n = 1'b1;
    reg sclk = 1'b0;
    reg mosi = 1'b0;
    wire miso;
    integer i;
    reg [7:0] command = 8'h9F;
    reg [23:0] captured = 24'h000000;

    hs_w25q_readonly_oracle dut(.cs_n(cs_n), .sclk(sclk), .mosi(mosi), .miso(miso));

    task clock_bit(input bit value);
        begin
            mosi = value;
            #5; sclk = 1'b1;
            #5; sclk = 1'b0;
        end
    endtask

    initial begin
        #10; cs_n = 1'b0;
        for (i = 7; i >= 0; i = i - 1) clock_bit(command[i]);
        // The derived oracle updates MISO on SCLK falling edges. Sample on the
        // following rising edge so the testbench does not race the DUT's
        // nonblocking assignment in the same simulation timestep.
        for (i = 23; i >= 0; i = i - 1) begin
            #5; sclk = 1'b1;
            captured[i] = miso;
            #5; sclk = 1'b0;
        end
        cs_n = 1'b1;
        if (captured !== 24'hEF6018) begin
            $display("FAIL captured=%h", captured);
            $finish_and_return(1);
        end
        $display("PASS JEDEC=%h", captured);
        $finish_and_return(0);
    end
endmodule
